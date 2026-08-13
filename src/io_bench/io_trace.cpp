#include "io_bench/io_trace.h"

#include <chrono>
#include <sstream>
#include <stdexcept>

namespace diskann::iobench
{
uint64_t monotonic_time_ns()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

IOTraceWriter::IOTraceWriter(const std::string &path)
{
    open(path);
}
IOTraceWriter::~IOTraceWriter()
{
    close();
}
void IOTraceWriter::open(const std::string &path)
{
    std::lock_guard<std::mutex> guard(mutex_);
    out_.open(path, std::ios::out | std::ios::trunc);
    if (!out_) throw std::runtime_error("Cannot open trace: " + path);
    out_ << "seq,timestamp_ns,query_id,thread_id,batch_id,request_in_batch,batch_size,offset,len,latency_ns,cache_miss\n";
    seq_.store(0);
    enabled_.store(true);
}
void IOTraceWriter::close()
{
    std::lock_guard<std::mutex> guard(mutex_);
    enabled_.store(false);
    if (out_.is_open()) out_.close();
}
void IOTraceWriter::append(const IOTraceRecord &r)
{
    append_batch({r});
}
void IOTraceWriter::append_batch(const std::vector<IOTraceRecord> &records)
{
    if (!enabled() || records.empty()) return;
    std::lock_guard<std::mutex> guard(mutex_);
    if (!enabled()) return;
    for (const auto &r : records)
        out_ << seq_.fetch_add(1) << ',' << r.timestamp_ns << ',' << r.query_id << ',' << r.thread_id << ','
             << r.batch_id << ',' << r.request_in_batch << ',' << r.batch_size << ',' << r.offset << ',' << r.len
             << ',' << r.latency_ns << ',' << static_cast<unsigned>(r.cache_miss) << '\n';
}

std::vector<IOTraceRecord> read_trace(const std::string &path)
{
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open trace: " + path);
    std::string line;
    std::getline(input, line);
    std::vector<IOTraceRecord> records;
    while (std::getline(input, line))
    {
        std::stringstream row(line);
        std::string field;
        uint64_t values[11]{};
        for (size_t i = 0; i < 11; ++i)
        {
            if (!std::getline(row, field, ',')) throw std::runtime_error("Malformed trace row: " + line);
            values[i] = std::stoull(field);
        }
        IOTraceRecord r;
        r.seq = values[0]; r.timestamp_ns = values[1]; r.query_id = values[2]; r.thread_id = values[3];
        r.batch_id = static_cast<uint32_t>(values[4]); r.request_in_batch = static_cast<uint32_t>(values[5]);
        r.batch_size = static_cast<uint32_t>(values[6]); r.offset = values[7]; r.len = values[8];
        r.latency_ns = values[9]; r.cache_miss = static_cast<uint8_t>(values[10]);
        records.push_back(r);
    }
    return records;
}
} // namespace diskann::iobench
