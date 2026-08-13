#include "io_bench/traced_aligned_file_reader.h"
#include "io_bench/query_context.h"

#include <functional>
#include <limits>
#include <thread>

namespace diskann::iobench
{
TracedAlignedFileReader::TracedAlignedFileReader(std::shared_ptr<AlignedFileReader> delegate,
                                                 std::shared_ptr<IOTraceWriter> trace)
    : delegate_(std::move(delegate)), trace_(std::move(trace)) {}
IOContext &TracedAlignedFileReader::get_ctx() { return delegate_->get_ctx(); }
void TracedAlignedFileReader::register_thread() { delegate_->register_thread(); }
void TracedAlignedFileReader::deregister_thread() { delegate_->deregister_thread(); }
void TracedAlignedFileReader::deregister_all_threads() { delegate_->deregister_all_threads(); }
void TracedAlignedFileReader::open(const std::string &fname) { delegate_->open(fname); }
void TracedAlignedFileReader::close() { delegate_->close(); }
void TracedAlignedFileReader::read(std::vector<AlignedRead> &reqs, IOContext &ctx, bool async)
{
    const uint32_t batch_id = next_batch();
    const uint64_t start = monotonic_time_ns();
    delegate_->read(reqs, ctx, async);
    const uint64_t latency = monotonic_time_ns() - start;
    if (current_query_io_context.query_id == std::numeric_limits<uint64_t>::max()) return;
    const uint64_t thread_id = std::hash<std::thread::id>{}(std::this_thread::get_id());
    std::vector<IOTraceRecord> records;
    records.reserve(reqs.size());
    for (size_t i = 0; i < reqs.size(); ++i)
    {
        IOTraceRecord r;
        r.timestamp_ns = start; r.query_id = current_query_io_context.query_id; r.thread_id = thread_id;
        r.batch_id = batch_id; r.request_in_batch = static_cast<uint32_t>(i);
        r.batch_size = static_cast<uint32_t>(reqs.size()); r.offset = reqs[i].offset; r.len = reqs[i].len;
        r.latency_ns = latency; r.cache_miss = 1; records.push_back(r);
    }
    trace_->append_batch(records);
}
} // namespace diskann::iobench
