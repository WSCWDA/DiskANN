#include "io_bench/io_trace.h"
#include <cassert>
#include <cstdio>
#include <unistd.h>

int main()
{
    char path[] = "/tmp/diskann-trace-XXXXXX";
    int fd = mkstemp(path); assert(fd >= 0); close(fd);
    diskann::iobench::IOTraceRecord expected;
    expected.timestamp_ns=2;expected.query_id=3;expected.thread_id=4;expected.batch_id=5;expected.request_in_batch=6;
    expected.batch_size=7;expected.offset=4096;expected.len=4096;expected.latency_ns=8;expected.cache_miss=1;
    { diskann::iobench::IOTraceWriter writer(path); writer.append(expected); }
    auto rows=diskann::iobench::read_trace(path);std::remove(path);assert(rows.size()==1);
    const auto &r=rows[0];assert(r.query_id==expected.query_id&&r.batch_id==expected.batch_id&&r.offset==expected.offset&&r.len==expected.len&&r.latency_ns==expected.latency_ns);
}
