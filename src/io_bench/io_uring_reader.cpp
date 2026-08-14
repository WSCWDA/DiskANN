#include "io_bench/io_uring_reader.h"

#if !defined(_WINDOWS) && defined(DISKANN_HAS_IO_URING)
#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <sys/uio.h>
#include <unistd.h>

namespace diskann::iobench
{
IoUringReader::IoUringReader()
{
    if (const char *value = std::getenv("DISKANN_IO_URING_TIMEOUT_MS"))
    {
        const unsigned long long parsed = std::strtoull(value, nullptr, 10);
        if (parsed > 0)
            completion_timeout_ms_ = parsed;
    }
    if (const char *value = std::getenv("DISKANN_IO_URING_MAX_BATCH"))
    {
        const unsigned long long parsed = std::strtoull(value, nullptr, 10);
        if (parsed > 0)
            max_batch_size_ = std::min<size_t>(parsed, MAX_IO_DEPTH);
    }
}
IoUringReader::~IoUringReader() { deregister_all_threads(); close(); }
IOContext &IoUringReader::get_ctx()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    const auto thread_id = std::this_thread::get_id();
    if (ctx_map.find(thread_id) == ctx_map.end())
    {
        return bad_ctx_;
    }
    return ctx_map[thread_id];
}
void IoUringReader::register_thread()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    const auto id = std::this_thread::get_id();
    if (rings_.find(id) != rings_.end()) return;
    auto *ring = new io_uring{};
    const int rc = io_uring_queue_init(MAX_IO_DEPTH, ring, 0);
    if (rc < 0) { delete ring; throw std::runtime_error("io_uring_queue_init: " + std::string(std::strerror(-rc))); }
    rings_[id] = ring;
    ctx_map[id] = IOContext{};
}
void IoUringReader::deregister_thread()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    const auto id = std::this_thread::get_id();
    auto it = rings_.find(id);
    if (it != rings_.end()) { io_uring_queue_exit(it->second); delete it->second; rings_.erase(it); }
    ctx_map.erase(id);
}
void IoUringReader::deregister_all_threads()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    for (auto &entry : rings_) { io_uring_queue_exit(entry.second); delete entry.second; }
    rings_.clear(); ctx_map.clear();
}
void IoUringReader::open(const std::string &fname)
{
    close(); fd_ = ::open(fname.c_str(), O_RDONLY | O_DIRECT | O_LARGEFILE);
    if (fd_ < 0) throw std::runtime_error("open(" + fname + ") failed: " + std::strerror(errno));
}
void IoUringReader::close() { if (fd_ >= 0) { ::close(fd_); fd_ = -1; } }
void IoUringReader::discard_current_thread_ring(io_uring *ring)
{
    // Tear down the ring before request-local iovecs leave scope. This asks
    // the kernel to cancel/reap outstanding requests and prevents a later
    // destructor from calling queue_exit on the same ring twice.
    io_uring_queue_exit(ring);
    std::lock_guard<std::mutex> guard(ctx_mut);
    const auto thread_id = std::this_thread::get_id();
    rings_.erase(thread_id);
    ctx_map.erase(thread_id);
    delete ring;
}
void IoUringReader::read(std::vector<AlignedRead> &reqs, IOContext &, bool)
{
    io_uring *ring = nullptr;
    { std::lock_guard<std::mutex> guard(ctx_mut); auto it = rings_.find(std::this_thread::get_id());
      if (it == rings_.end()) throw std::runtime_error("io-uring thread is not registered"); ring = it->second; }
    for (size_t base = 0; base < reqs.size(); base += max_batch_size_)
    {
        const size_t count = std::min<size_t>(max_batch_size_, reqs.size() - base);
        // IORING_OP_READV is supported by older io_uring kernels than
        // IORING_OP_READ. Keep the iovec array alive until all CQEs arrive.
        // One AlignedRead still maps to exactly one SQE and one iovec.
        std::vector<iovec> iovecs(count);
        for (size_t i = 0; i < count; ++i)
        {
            io_uring_sqe *sqe = io_uring_get_sqe(ring);
            if (!sqe) throw std::runtime_error("No io_uring SQE");
            auto &req = reqs[base + i];
            iovecs[i].iov_base = req.buf;
            iovecs[i].iov_len = req.len;
            io_uring_prep_readv(sqe, fd_, &iovecs[i], 1, req.offset);
            io_uring_sqe_set_data64(sqe, base + i);
        }
        const int submitted = io_uring_submit(ring);
        if (submitted != static_cast<int>(count)) throw std::runtime_error("io_uring partial submission");
        for (size_t i = 0; i < count; ++i)
        {
            io_uring_cqe *cqe = nullptr;
            __kernel_timespec timeout{};
            timeout.tv_sec = completion_timeout_ms_ / 1000;
            timeout.tv_nsec = (completion_timeout_ms_ % 1000) * 1000000;
            const int rc = io_uring_wait_cqe_timeout(ring, &cqe, &timeout);
            if (rc == -ETIME)
            {
                const std::string message =
                    "io_uring completion timeout after " + std::to_string(completion_timeout_ms_) +
                    " ms: batch_start=" + std::to_string(base) + ", batch_size=" + std::to_string(count) +
                    ", completed=" + std::to_string(i) + ", remaining=" + std::to_string(count - i);
                discard_current_thread_ring(ring);
                throw std::runtime_error(message);
            }
            if (rc < 0) throw std::runtime_error("io_uring_wait_cqe: " + std::string(std::strerror(-rc)));
            const size_t index = io_uring_cqe_get_data64(cqe);
            const int result = cqe->res;
            io_uring_cqe_seen(ring, cqe);
            if (result < 0)
                throw std::runtime_error("io_uring read failed at offset " +
                                         std::to_string(reqs[index].offset) + ": " +
                                         std::string(std::strerror(-result)));
            if (result != static_cast<int>(reqs[index].len))
                throw std::runtime_error("io_uring short read at offset " +
                                         std::to_string(reqs[index].offset) + ": returned " +
                                         std::to_string(result) + ", expected " +
                                         std::to_string(reqs[index].len));
        }
    }
}
} // namespace diskann::iobench
#endif
