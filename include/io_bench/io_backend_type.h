#pragma once

#include <stdexcept>
#include <string>

namespace diskann::iobench
{
enum class IOBackendType
{
    LIBAIO,
    PREAD_DIRECT,
    PREAD_BUFFERED,
    IO_URING,
    GDS
};

inline IOBackendType parse_io_backend(const std::string &value)
{
    if (value == "libaio") return IOBackendType::LIBAIO;
    if (value == "pread-direct") return IOBackendType::PREAD_DIRECT;
    if (value == "pread-buffered") return IOBackendType::PREAD_BUFFERED;
    if (value == "io-uring") return IOBackendType::IO_URING;
    if (value == "gds") return IOBackendType::GDS;
    throw std::invalid_argument("Unknown I/O backend: " + value);
}

inline const char *to_string(IOBackendType type)
{
    switch (type)
    {
    case IOBackendType::LIBAIO: return "libaio";
    case IOBackendType::PREAD_DIRECT: return "pread-direct";
    case IOBackendType::PREAD_BUFFERED: return "pread-buffered";
    case IOBackendType::IO_URING: return "io-uring";
    case IOBackendType::GDS: return "gds";
    }
    return "unknown";
}
} // namespace diskann::iobench
