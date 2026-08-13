#include "io_bench/posix_aligned_file_reader.h"

#ifndef _WINDOWS
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <unistd.h>

namespace diskann::iobench
{
PosixAlignedFileReader::PosixAlignedFileReader(bool direct) : direct_(direct) {}
PosixAlignedFileReader::~PosixAlignedFileReader() { close(); }
IOContext &PosixAlignedFileReader::get_ctx()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    auto it = ctx_map.find(std::this_thread::get_id());
    return it == ctx_map.end() ? bad_ctx_ : it->second;
}
void PosixAlignedFileReader::register_thread()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    ctx_map.emplace(std::this_thread::get_id(), IOContext{});
}
void PosixAlignedFileReader::deregister_thread()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    ctx_map.erase(std::this_thread::get_id());
}
void PosixAlignedFileReader::deregister_all_threads()
{
    std::lock_guard<std::mutex> guard(ctx_mut);
    ctx_map.clear();
}
void PosixAlignedFileReader::open(const std::string &fname)
{
    close();
    int flags = O_RDONLY | O_LARGEFILE;
    if (direct_) flags |= O_DIRECT;
    fd_ = ::open(fname.c_str(), flags);
    if (fd_ < 0) throw std::runtime_error("open(" + fname + ") failed: " + std::strerror(errno));
}
void PosixAlignedFileReader::close()
{
    if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
}
void PosixAlignedFileReader::read(std::vector<AlignedRead> &reqs, IOContext &, bool)
{
    if (fd_ < 0) throw std::runtime_error("reader is not open");
    for (auto &req : reqs)
    {
        size_t done = 0;
        while (done < req.len)
        {
            const ssize_t n = ::pread(fd_, static_cast<char *>(req.buf) + done, req.len - done, req.offset + done);
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0) throw std::runtime_error("pread failed at offset " + std::to_string(req.offset + done) +
                                                 ": " + std::strerror(errno));
            done += static_cast<size_t>(n);
        }
    }
}
} // namespace diskann::iobench
#endif
