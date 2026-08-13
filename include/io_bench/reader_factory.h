#pragma once

#include "aligned_file_reader.h"
#include <memory>
#include <string>

namespace diskann::iobench
{
std::shared_ptr<AlignedFileReader> create_reader(const std::string &backend, const std::string &trace_path = "");
}
