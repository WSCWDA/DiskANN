#pragma once

#if !defined(_WINDOWS) && defined(DISKANN_HAS_GDS)

#include "aligned_file_reader.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include <cufile.h>

namespace diskann::iobench
{
// GPU destination reader used only by replay_diskann_trace. It deliberately
// does not implement AlignedFileReader: CPU PQFlashIndex consumes host buffers,
// while this class measures the SSD-to-HBM path without an implicit D2H copy.
class GDSReplayReader final
{
  public:
    GDSReplayReader(int device_id, size_t buffer_capacity);
    ~GDSReplayReader();

    GDSReplayReader(const GDSReplayReader &) = delete;
    GDSReplayReader &operator=(const GDSReplayReader &) = delete;

    void open(const std::string &filename);
    void close() noexcept;
    void read(const std::vector<AlignedRead> &requests);
    void copy_to_host(const std::vector<AlignedRead> &requests);

  private:
    size_t validate_and_measure(const std::vector<AlignedRead> &requests) const;

    int device_id_ = 0;
    int fd_ = -1;
    size_t buffer_capacity_ = 0;
    void *device_buffer_ = nullptr;
    CUfileHandle_t file_handle_{};
    bool driver_open_ = false;
    bool handle_registered_ = false;
    bool buffer_registered_ = false;
};
} // namespace diskann::iobench

#endif
