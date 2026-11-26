#include "qshape/shared_io_coordinator.h"
#include <iostream>
#include <random>
int main(int argc,char** argv){
 using namespace qshape;
 uint64_t n=argc>1?std::stoull(argv[1]):100000,ops=argc>2?std::stoull(argv[2]):1000000;
 if(!n||!ops)return 1;
 FrequencySketch s;s.init(16384,4);std::unordered_map<Key,uint64_t,Hash> exact;
 std::vector<uint64_t> keys;keys.reserve(ops);std::mt19937_64 rng(42);
 for(uint64_t i=0;i<ops;++i)keys.push_back(rng()%n*4096);
 auto t=now_ns();for(auto k:keys)++exact[{k,4096}];auto exact_ns=now_ns()-t;
 t=now_ns();for(auto k:keys)s.increment(k,4096);auto cms_ns=now_ns()-t;
 uint64_t error=0;for(auto& p:exact)error+=s.estimate(p.first.offset,p.first.length)-p.second;
 std::cout<<"unique,ops,exact_update_ns,cms_update_ns,cms_bytes,exact_field_bytes,mean_overestimate\n"<<exact.size()<<','<<ops<<','<<exact_ns<<','<<cms_ns<<','<<s.bytes()<<','<<exact.size()*24<<','<<double(error)/exact.size()<<'\n';
}
