#pragma once

#ifndef _WINDOWS
#include "aligned_file_reader.h"

namespace diskann::iobench
{
class PosixAlignedFileReader : public AlignedFileReader
{
  public:
    explicit PosixAlignedFileReader(bool direct);
    ~PosixAlignedFileReader() override;
    IOContext &get_ctx() override;
    void register_thread() override;
    void deregister_thread() override;
    void deregister_all_threads() override;
    void open(const std::string &fname) override;
    void close() override;
    void read(std::vector<AlignedRead> &read_reqs, IOContext &ctx, bool async = false) override;

  private:
    bool direct_;
    int fd_ = -1;
    IOContext bad_ctx_ = (IOContext)-1;
};

class PreadDirectReader final : public PosixAlignedFileReader
{
  public:
    PreadDirectReader() : PosixAlignedFileReader(true) {}
};
class PreadBufferedReader final : public PosixAlignedFileReader
{
  public:
    PreadBufferedReader() : PosixAlignedFileReader(false) {}
};
} // namespace diskann::iobench
#endif
