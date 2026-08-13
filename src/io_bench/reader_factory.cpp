#include "io_bench/reader_factory.h"
#include "io_bench/io_backend_type.h"
#include "io_bench/traced_aligned_file_reader.h"

#ifndef _WINDOWS
#include "io_bench/io_uring_reader.h"
#include "io_bench/posix_aligned_file_reader.h"
#include "linux_aligned_file_reader.h"
#endif

namespace diskann::iobench
{
std::shared_ptr<AlignedFileReader> create_reader(const std::string &backend, const std::string &trace_path)
{
    const auto type = parse_io_backend(backend);
    std::shared_ptr<AlignedFileReader> reader;
#ifndef _WINDOWS
    if (type == IOBackendType::LIBAIO) reader = std::make_shared<LinuxAlignedFileReader>();
    else if (type == IOBackendType::PREAD_DIRECT) reader = std::make_shared<PreadDirectReader>();
    else if (type == IOBackendType::PREAD_BUFFERED) reader = std::make_shared<PreadBufferedReader>();
#ifdef DISKANN_HAS_IO_URING
    else if (type == IOBackendType::IO_URING) reader = std::make_shared<IoUringReader>();
#else
    else if (type == IOBackendType::IO_URING) throw std::runtime_error("io-uring backend was not built");
#endif
    else if (type == IOBackendType::GDS) throw std::runtime_error("GDS backend was not built");
#else
    (void)type;
    throw std::runtime_error("DiskANN I/O benchmark backends are Linux-only");
#endif
    if (!trace_path.empty())
        reader = std::make_shared<TracedAlignedFileReader>(reader, std::make_shared<IOTraceWriter>(trace_path));
    return reader;
}
} // namespace diskann::iobench
