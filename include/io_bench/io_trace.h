#pragma once

#include <atomic>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>
#include <vector>

namespace diskann::iobench
{
struct IOTraceRecord
{
    uint64_t seq = 0;
    uint64_t timestamp_ns = 0;
    uint64_t query_id = 0;
    uint64_t thread_id = 0;
    uint32_t batch_id = 0;
    uint32_t request_in_batch = 0;
    uint32_t batch_size = 0;
    uint64_t offset = 0;
    uint64_t len = 0;
    uint64_t latency_ns = 0;
    uint8_t cache_miss = 1;
};

class IOTraceWriter
{
  public:
    IOTraceWriter() = default;
    explicit IOTraceWriter(const std::string &path);
    ~IOTraceWriter();
    void open(const std::string &path);
    void close();
    void append(const IOTraceRecord &record);
    void append_batch(const std::vector<IOTraceRecord> &records);
    bool enabled() const { return enabled_.load(std::memory_order_relaxed); }

  private:
    std::ofstream out_;
    std::mutex mutex_;
    std::atomic<uint64_t> seq_{0};
    std::atomic<bool> enabled_{false};
};

std::vector<IOTraceRecord> read_trace(const std::string &path);
uint64_t monotonic_time_ns();
} // namespace diskann::iobench
