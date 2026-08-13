#pragma once

#include "aligned_file_reader.h"
#include "io_bench/io_trace.h"
#include <memory>

namespace diskann::iobench
{
class TracedAlignedFileReader final : public AlignedFileReader
{
  public:
    TracedAlignedFileReader(std::shared_ptr<AlignedFileReader> delegate, std::shared_ptr<IOTraceWriter> trace);
    IOContext &get_ctx() override;
    void register_thread() override;
    void deregister_thread() override;
    void deregister_all_threads() override;
    void open(const std::string &fname) override;
    void close() override;
    void read(std::vector<AlignedRead> &read_reqs, IOContext &ctx, bool async = false) override;

  private:
    std::shared_ptr<AlignedFileReader> delegate_;
    std::shared_ptr<IOTraceWriter> trace_;
};
} // namespace diskann::iobench
