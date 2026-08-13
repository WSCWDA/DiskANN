#pragma once

#if !defined(_WINDOWS) && defined(DISKANN_HAS_IO_URING)
#include "aligned_file_reader.h"
#include <liburing.h>

namespace diskann::iobench
{
class IoUringReader final : public AlignedFileReader
{
  public:
    IoUringReader();
    ~IoUringReader() override;
    IOContext &get_ctx() override;
    void register_thread() override;
    void deregister_thread() override;
    void deregister_all_threads() override;
    void open(const std::string &fname) override;
    void close() override;
    void read(std::vector<AlignedRead> &read_reqs, IOContext &ctx, bool async = false) override;

  private:
    int fd_ = -1;
    IOContext bad_ctx_ = (IOContext)-1;
    tsl::robin_map<std::thread::id, io_uring *> rings_;
};
} // namespace diskann::iobench
#endif
