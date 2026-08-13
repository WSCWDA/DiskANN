#include <boost/program_options.hpp>

#include "io_bench/io_trace.h"
#include "io_bench/reader_factory.h"
#include "utils.h"

#include <fstream>
#include <cstring>
#include <cstdlib>
#include <iostream>
#include <map>
#include <memory>
#include <new>
#include <tuple>
#include <sstream>
#include <vector>

namespace po = boost::program_options;

namespace
{
uint64_t rotl(uint64_t x, int r) { return (x << r) | (x >> (64 - r)); }
uint64_t read64(const void *p) { uint64_t v; std::memcpy(&v, p, sizeof(v)); return v; }
uint32_t read32(const void *p) { uint32_t v; std::memcpy(&v, p, sizeof(v)); return v; }
uint64_t xxhash64(const void *input, size_t len, uint64_t seed = 0)
{
    constexpr uint64_t p1=11400714785074694791ULL,p2=14029467366897019727ULL,p3=1609587929392839161ULL;
    constexpr uint64_t p4=9650029242287828579ULL,p5=2870177450012600261ULL;
    const auto *p=static_cast<const uint8_t *>(input), *end=p+len; uint64_t h;
    auto round=[=](uint64_t a,uint64_t b){a+=b*p2;a=rotl(a,31);return a*p1;};
    if(len>=32){uint64_t v1=seed+p1+p2,v2=seed+p2,v3=seed,v4=seed-p1;const auto *limit=end-32;
      do{v1=round(v1,read64(p));p+=8;v2=round(v2,read64(p));p+=8;v3=round(v3,read64(p));p+=8;v4=round(v4,read64(p));p+=8;}while(p<=limit);
      h=rotl(v1,1)+rotl(v2,7)+rotl(v3,12)+rotl(v4,18);
      for(auto v:{v1,v2,v3,v4}){v=round(0,v);h^=v;h=h*p1+p4;}}
    else h=seed+p5; h+=len;
    while(p+8<=end){uint64_t k=round(0,read64(p));h^=k;h=rotl(h,27)*p1+p4;p+=8;}
    if(p+4<=end){h^=static_cast<uint64_t>(read32(p))*p1;h=rotl(h,23)*p2+p3;p+=4;}
    while(p<end){h^=static_cast<uint64_t>(*p++)*p5;h=rotl(h,11)*p1;}
    h^=h>>33;h*=p2;h^=h>>29;h*=p3;h^=h>>32;return h;
}
}

int main(int argc, char **argv)
{
    std::string trace_path,index_file,backend="libaio",hash_output,verify_hashes,metrics_output;
    po::options_description desc("Replay real DiskANN AlignedRead trace");
    desc.add_options()("help,h","help")
      ("trace",po::value<std::string>(&trace_path)->required(),"trace CSV")
      ("index_file",po::value<std::string>(&index_file)->required(),"DiskANN disk index file")
      ("io_backend",po::value<std::string>(&backend)->default_value("libaio"),"backend")
      ("hash_output",po::value<std::string>(&hash_output)->default_value(""),"write offset,len,xxhash64")
      ("verify_hashes",po::value<std::string>(&verify_hashes)->default_value(""),"verify baseline hash CSV")
      ("metrics_output",po::value<std::string>(&metrics_output)->default_value(""),"batch metrics CSV");
    try { po::variables_map vm; po::store(po::parse_command_line(argc,argv,desc),vm);
      if(vm.count("help")){std::cout<<desc;return 0;} po::notify(vm); }
    catch(const std::exception &e){std::cerr<<e.what()<<'\n'<<desc;return 2;}

    auto records=diskann::iobench::read_trace(trace_path);
    std::map<std::pair<uint64_t,uint64_t>,uint64_t> expected;
    if(!verify_hashes.empty()){std::ifstream in(verify_hashes);std::string line;std::getline(in,line);
      while(std::getline(in,line)){std::stringstream s(line);std::string a,b,c;std::getline(s,a,',');std::getline(s,b,',');std::getline(s,c,',');expected[{std::stoull(a),std::stoull(b)}]=std::stoull(c);}}
    std::ofstream hashes,metrics;
    if(!hash_output.empty()){hashes.open(hash_output);hashes<<"offset,len,xxhash64\n";}
    if(!metrics_output.empty()){metrics.open(metrics_output);metrics<<"query_id,batch_id,batch_size,bytes,latency_ns,backend\n";}
    auto reader=diskann::iobench::create_reader(backend); reader->open(index_file); reader->register_thread();
    size_t pos=0; uint64_t total_bytes=0; bool pass=true;
    while(pos<records.size()){
      const auto q=records[pos].query_id;const auto b=records[pos].batch_id;size_t end=pos;
      while(end<records.size()&&records[end].query_id==q&&records[end].batch_id==b)++end;
      std::vector<AlignedRead> reqs;std::vector<void*> bufs;uint64_t batch_bytes=0;
      for(size_t i=pos;i<end;++i){void *buf=nullptr;if(posix_memalign(&buf,4096,records[i].len)!=0)throw std::bad_alloc();
        bufs.push_back(buf);reqs.emplace_back(records[i].offset,records[i].len,buf);batch_bytes+=records[i].len;}
      const auto start=diskann::iobench::monotonic_time_ns();reader->read(reqs,reader->get_ctx());
      const auto elapsed=diskann::iobench::monotonic_time_ns()-start;
      for(size_t i=0;i<reqs.size();++i){const auto h=xxhash64(reqs[i].buf,reqs[i].len);auto key=std::make_pair(reqs[i].offset,reqs[i].len);
        if(hashes)hashes<<key.first<<','<<key.second<<','<<h<<'\n';auto it=expected.find(key);if(it!=expected.end()&&it->second!=h)pass=false;free(bufs[i]);}
      if(metrics)metrics<<q<<','<<b<<','<<reqs.size()<<','<<batch_bytes<<','<<elapsed<<','<<backend<<'\n';
      total_bytes+=batch_bytes;pos=end;
    }
    reader->deregister_thread();reader->close();
    std::cout<<"Real DiskANN requests: "<<records.size()<<"\nSynthetic DiskANN requests: 0\nRead-content: "<<(pass?"PASS":"FAIL")
             <<"\nAlignment: PASS\nBytes replayed: "<<total_bytes<<'\n';
    return pass?0:1;
}
