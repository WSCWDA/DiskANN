#include "io_bench/reader_factory.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <string>
#include <unistd.h>
#include <vector>

int main()
{
    char path[] = "/tmp/diskann-reader-XXXXXX";
    const int fd = mkstemp(path); assert(fd >= 0);
    std::vector<unsigned char> expected(8192);
    for (size_t i=0;i<expected.size();++i) expected[i]=static_cast<unsigned char>((i*131U+17U)&255U);
    assert(write(fd,expected.data(),expected.size())==static_cast<ssize_t>(expected.size())); close(fd);
    std::vector<std::string> backends={"libaio","pread-direct","pread-buffered"};
#ifdef DISKANN_HAS_IO_URING
    backends.push_back("io-uring");
#endif
    for(const auto &backend:backends){auto reader=diskann::iobench::create_reader(backend);reader->open(path);reader->register_thread();
      void *buffer=nullptr;assert(posix_memalign(&buffer,4096,4096)==0);std::vector<AlignedRead> reads;reads.emplace_back(4096,4096,buffer);
      reader->read(reads,reader->get_ctx());assert(std::memcmp(buffer,expected.data()+4096,4096)==0);free(buffer);reader->deregister_thread();reader->close();}
    std::remove(path);
}
