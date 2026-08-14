#include "io_bench/gds_replay_reader.h"

#if !defined(_WINDOWS) && defined(DISKANN_HAS_GDS)

#include <cuda_runtime_api.h>

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <unistd.h>

namespace diskann::iobench
{
namespace
{
constexpr size_t GDS_ALIGNMENT = 4096;

std::runtime_error cuda_error(const char *operation, cudaError_t status)
{
    return std::runtime_error(std::string(operation) + ": " + cudaGetErrorString(status));
}

std::runtime_error cufile_error(const char *operation, CUfileError_t status)
{
    return std::runtime_error(std::string(operation) + ": " + cuFileGetErrorString(status));
}
} // namespace

GDSReplayReader::GDSReplayReader(int device_id, size_t buffer_capacity)
    : device_id_(device_id), buffer_capacity_(buffer_capacity)
{
    if (buffer_capacity_ == 0 || buffer_capacity_ % GDS_ALIGNMENT != 0)
        throw std::invalid_argument("GDS buffer capacity must be a non-zero multiple of 4096");

    cudaError_t cuda_status = cudaSetDevice(device_id_);
    if (cuda_status != cudaSuccess) throw cuda_error("cudaSetDevice", cuda_status);

    CUfileError_t cufile_status = cuFileDriverOpen();
    if (cufile_status.err != CU_FILE_SUCCESS) throw cufile_error("cuFileDriverOpen", cufile_status);
    driver_open_ = true;

    cuda_status = cudaMalloc(&device_buffer_, buffer_capacity_);
    if (cuda_status != cudaSuccess)
    {
        close();
        throw cuda_error("cudaMalloc", cuda_status);
    }

    cufile_status = cuFileBufRegister(device_buffer_, buffer_capacity_, 0);
    if (cufile_status.err != CU_FILE_SUCCESS)
    {
        close();
        throw cufile_error("cuFileBufRegister", cufile_status);
    }
    buffer_registered_ = true;
}

GDSReplayReader::~GDSReplayReader() { close(); }

void GDSReplayReader::open(const std::string &filename)
{
    if (fd_ >= 0) throw std::runtime_error("GDS replay reader is already open");
    fd_ = ::open(filename.c_str(), O_RDONLY | O_DIRECT | O_LARGEFILE);
    if (fd_ < 0) throw std::runtime_error("open(" + filename + ") failed: " + std::strerror(errno));

    CUfileDescr_t descriptor{};
    descriptor.handle.fd = fd_;
    descriptor.type = CU_FILE_HANDLE_TYPE_OPAQUE_FD;
    const CUfileError_t status = cuFileHandleRegister(&file_handle_, &descriptor);
    if (status.err != CU_FILE_SUCCESS)
    {
        ::close(fd_);
        fd_ = -1;
        throw cufile_error("cuFileHandleRegister", status);
    }
    handle_registered_ = true;
}

void GDSReplayReader::close() noexcept
{
    if (handle_registered_)
    {
        cuFileHandleDeregister(file_handle_);
        handle_registered_ = false;
    }
    if (fd_ >= 0)
    {
        ::close(fd_);
        fd_ = -1;
    }
    if (buffer_registered_)
    {
        cuFileBufDeregister(device_buffer_);
        buffer_registered_ = false;
    }
    if (device_buffer_ != nullptr)
    {
        cudaFree(device_buffer_);
        device_buffer_ = nullptr;
    }
    if (driver_open_)
    {
        cuFileDriverClose();
        driver_open_ = false;
    }
}

size_t GDSReplayReader::validate_and_measure(const std::vector<AlignedRead> &requests) const
{
    size_t bytes = 0;
    for (const auto &request : requests)
    {
        if (request.offset % GDS_ALIGNMENT != 0 || request.len == 0 || request.len % GDS_ALIGNMENT != 0)
            throw std::runtime_error("GDS trace request offset and length must be 4096-byte aligned");
        if (request.buf == nullptr) throw std::runtime_error("GDS verification buffer is null");
        if (request.len > buffer_capacity_ || bytes > buffer_capacity_ - request.len)
            throw std::runtime_error("GDS replay batch exceeds GPU buffer");
        bytes += request.len;
    }
    return bytes;
}

void GDSReplayReader::read(const std::vector<AlignedRead> &requests)
{
    if (!handle_registered_) throw std::runtime_error("GDS replay reader is not open");
    validate_and_measure(requests);
    off_t device_offset = 0;
    for (const auto &request : requests)
    {
        const ssize_t result = cuFileRead(file_handle_, device_buffer_, request.len, request.offset, device_offset);
        if (result < 0)
            throw std::runtime_error("cuFileRead failed at offset " + std::to_string(request.offset) +
                                     ": status=" + std::to_string(result));
        if (result != static_cast<ssize_t>(request.len))
            throw std::runtime_error("cuFileRead short read at offset " + std::to_string(request.offset) +
                                     ": returned " + std::to_string(result) + ", expected " +
                                     std::to_string(request.len));
        device_offset += static_cast<off_t>(request.len);
    }
}

void GDSReplayReader::copy_to_host(const std::vector<AlignedRead> &requests)
{
    validate_and_measure(requests);
    size_t device_offset = 0;
    for (const auto &request : requests)
    {
        const cudaError_t status = cudaMemcpy(request.buf, static_cast<char *>(device_buffer_) + device_offset,
                                              request.len, cudaMemcpyDeviceToHost);
        if (status != cudaSuccess) throw cuda_error("cudaMemcpy(DeviceToHost)", status);
        device_offset += request.len;
    }
}
} // namespace diskann::iobench

#endif
