#include "io_bench/io_uring_reader.h"

#if !defined(_WINDOWS) && defined(DISKANN_HAS_IO_URING)
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <unistd.h>

namespace diskann::iobench
{
IoUringReader::IoUringReader() = default;
IoUringReader::~IoUringReader() { deregister_all_threads(); close(); }
IOContext &IoUringReader::get_ctx()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    auto it = ctx_map.find(std::this_thread::get_id());
    return it == ctx_map.end() ? bad_ctx_ : it->second;
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
void IoUringReader::read(std::vector<AlignedRead> &reqs, IOContext &, bool)
{
    io_uring *ring = nullptr;
    { std::lock_guard<std::mutex> guard(ctx_mut); auto it = rings_.find(std::this_thread::get_id());
      if (it == rings_.end()) throw std::runtime_error("io-uring thread is not registered"); ring = it->second; }
    for (size_t base = 0; base < reqs.size(); base += MAX_IO_DEPTH)
    {
        const size_t count = std::min<size_t>(MAX_IO_DEPTH, reqs.size() - base);
        for (size_t i = 0; i < count; ++i)
        {
            io_uring_sqe *sqe = io_uring_get_sqe(ring);
            if (!sqe) throw std::runtime_error("No io_uring SQE");
            auto &req = reqs[base + i];
            io_uring_prep_read(sqe, fd_, req.buf, static_cast<unsigned>(req.len), req.offset);
            io_uring_sqe_set_data64(sqe, base + i);
        }
        const int submitted = io_uring_submit(ring);
        if (submitted != static_cast<int>(count)) throw std::runtime_error("io_uring partial submission");
        for (size_t i = 0; i < count; ++i)
        {
            io_uring_cqe *cqe = nullptr;
            const int rc = io_uring_wait_cqe(ring, &cqe);
            if (rc < 0) throw std::runtime_error("io_uring_wait_cqe: " + std::string(std::strerror(-rc)));
            const size_t index = io_uring_cqe_get_data64(cqe);
            const int result = cqe->res;
            io_uring_cqe_seen(ring, cqe);
            if (result != static_cast<int>(reqs[index].len))
                throw std::runtime_error("io_uring read returned " + std::to_string(result));
        }
    }
}
} // namespace diskann::iobench
#endif
