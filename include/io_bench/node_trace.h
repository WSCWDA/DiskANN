#pragma once
// Optional per-query node event trace. Set DISKANN_NODE_TRACE_PATH to enable.
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <mutex>
#include <string>
#include <vector>
#include "io_bench/query_context.h"

namespace diskann::iobench {
struct NodeEvent {
    uint64_t query_id, timestamp_ns, offset;
    uint32_t batch_id, node_id, degree;
    const char *event;
};
inline uint64_t node_trace_now_ns() {
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
class NodeTrace {
public:
    NodeTrace() : path_(std::getenv("DISKANN_NODE_TRACE_PATH") ? std::getenv("DISKANN_NODE_TRACE_PATH") : ""),
                  query_id_(current_query_io_context.query_id) {
        if (query_id_ == UINT64_MAX) path_.clear();
    }
    NodeTrace(const NodeTrace &) = delete;
    NodeTrace &operator=(const NodeTrace &) = delete;
    void add(const char *event, uint32_t node_id, uint64_t offset, uint32_t degree = 0) {
        if (path_.empty()) return;
        events_.push_back({query_id_, node_trace_now_ns(), offset,
                           current_query_io_context.batch_id, node_id, degree, event});
    }
    ~NodeTrace() noexcept {
        if (events_.empty()) return;
        try {
            static std::mutex mutex;
            std::lock_guard<std::mutex> lock(mutex);
            std::ifstream existing(path_);
            const bool header = !existing.good() || existing.peek() == std::ifstream::traits_type::eof();
            existing.close();
            std::ofstream out(path_, std::ios::app);
            if (!out) return;
            if (header) out << "query_id,batch_id,node_id,offset,event_type,degree,timestamp_ns\n";
            for (const auto &e : events_)
                out << e.query_id << ',' << e.batch_id << ',' << e.node_id << ','
                    << e.offset << ',' << e.event << ',' << e.degree << ',' << e.timestamp_ns << '\n';
        } catch (...) { /* tracing must never break search */ }
    }
private:
    std::string path_;
    uint64_t query_id_;
    std::vector<NodeEvent> events_;
};
} // namespace diskann::iobench
