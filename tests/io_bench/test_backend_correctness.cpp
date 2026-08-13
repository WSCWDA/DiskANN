#include "io_bench/reader_factory.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <vector>

int main()
{
    char path[] = "/tmp/diskann-reader-XXXXXX";
    const int fd = mkstemp(path);
    if (fd < 0)
        throw std::runtime_error("mkstemp failed");
    std::vector<unsigned char> expected(8192);
    for (size_t i=0;i<expected.size();++i) expected[i]=static_cast<unsigned char>((i*131U+17U)&255U);
    const ssize_t written = write(fd, expected.data(), expected.size());
    if (written != static_cast<ssize_t>(expected.size()))
        throw std::runtime_error("failed to initialize backend test file");
    if (fsync(fd) != 0 || close(fd) != 0)
        throw std::runtime_error("failed to finalize backend test file");
    std::vector<std::string> backends={"libaio","pread-direct","pread-buffered"};
#ifdef DISKANN_HAS_IO_URING
    backends.push_back("io-uring");
#endif
    for(const auto &backend:backends){auto reader=diskann::iobench::create_reader(backend);reader->open(path);reader->register_thread();
      void *buffer=nullptr;if(posix_memalign(&buffer,4096,4096)!=0)throw std::bad_alloc();std::memset(buffer,0,4096);std::vector<AlignedRead> reads;reads.emplace_back(4096,4096,buffer);
      reader->read(reads,reader->get_ctx());if(std::memcmp(buffer,expected.data()+4096,4096)!=0)throw std::runtime_error("backend returned incorrect bytes: "+backend);free(buffer);reader->deregister_thread();reader->close();}
    std::remove(path);
}
