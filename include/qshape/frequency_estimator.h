#pragma once
#include <cstdint>
#include <cstddef>
#include <memory>
#include <algorithm>
#include <stdexcept>
namespace qshape {
class FrequencySketch {
 std::unique_ptr<uint32_t[]> counters;
 size_t width=0,depth=0;
 static uint64_t mix(uint64_t x){x^=x>>30;x*=0xbf58476d1ce4e5b9ULL;x^=x>>27;x*=0x94d049bb133111ebULL;return x^(x>>31);}
 size_t slot(uint64_t off,uint64_t len,size_t row)const{
  return row*width+mix(mix(off+0x9e3779b97f4a7c15ULL*(row+1))^mix(len+0xd1b54a32d192ed03ULL*(row+1)))%width;
 }
public:
 void init(size_t bytes,size_t d){
  if(!d||d>8||bytes/sizeof(uint32_t)/d==0)throw std::invalid_argument("invalid sketch budget/depth");
  size_t w=bytes/sizeof(uint32_t)/d;
  auto p=std::unique_ptr<uint32_t[]>(new uint32_t[w*d]());
  counters=std::move(p);width=w;depth=d;
 }
 size_t bytes()const{return width*depth*sizeof(uint32_t);}
 void clear(){if(counters)std::fill_n(counters.get(),width*depth,0);}
 uint64_t increment(uint64_t off,uint64_t len){
  uint64_t saturated=0;
  for(size_t i=0;i<depth;++i){auto& c=counters[slot(off,len,i)];if(c==UINT32_MAX)++saturated;else ++c;}
  return saturated;
 }
 uint64_t estimate(uint64_t off,uint64_t len)const{
  if(!depth)return 0;
  uint32_t n=UINT32_MAX;for(size_t i=0;i<depth;++i)n=std::min(n,counters[slot(off,len,i)]);return n;
 }
};
}
