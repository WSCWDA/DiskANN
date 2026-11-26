#pragma once
#include "qshape/shared_io_coordinator.h"
#include <random>
#include <numeric>
#include <cmath>
#include <thread>
#include <atomic>
#include <stdexcept>
namespace esc {
using namespace qshape;
struct Workload {
 uint64_t n,seed; double skew; std::vector<double> cdf;
 Workload(uint64_t n_,uint64_t seed_,double s):n(n_),seed(seed_),skew(s){
  if(!n||n>10000000||!std::isfinite(s)||s<0)throw std::invalid_argument("workload");
  if(s){cdf.resize(n);double sum=0;for(size_t i=0;i<n;++i)cdf[i]=sum+=std::pow(double(i+1),-s);}
 }
 uint64_t next(std::mt19937_64& rng)const{
  if(!skew)return rng()%n;
  double x=std::generate_canonical<double,53>(rng)*cdf.back();
  return std::min<uint64_t>(n-1,std::upper_bound(cdf.begin(),cdf.end(),x)-cdf.begin());
 }
};
struct Estimator {
 struct Shard {std::mutex lock; FrequencySketch cms; std::unordered_map<Key,uint64_t,Hash> exact;};
 std::array<Shard,64> shards; bool sketch;
 Estimator(bool s,size_t budget):sketch(s){if(s)for(auto& x:shards)x.cms.init(budget/64,4);}
 static Key key(uint64_t id){return {id*4096,4096};}
 uint64_t apply(uint64_t id,bool update,unsigned estimates,uint64_t& sat){
  auto k=key(id);auto& sh=shards[Hash{}(k)%64];std::lock_guard<std::mutex> guard(sh.lock);
  if(update){if(sketch)sat+=sh.cms.increment(k.offset,k.length);else ++sh.exact[k];}
  uint64_t sum=0;for(unsigned j=0;j<estimates;++j){
   if(sketch)sum+=sh.cms.estimate(k.offset,k.length);
   else {auto it=sh.exact.find(k);if(it!=sh.exact.end())sum+=it->second;}
  }return sum;
 }
 uint64_t bytes()const{uint64_t n=0;for(auto& s:shards)n+=sketch?s.cms.bytes():s.exact.size()*24;return n;}
 uint64_t entries()const{uint64_t n=0;for(auto& s:shards)n+=s.exact.size();return n;}
};
inline std::vector<uint64_t> top(const std::vector<uint64_t>& counts,size_t k){
 std::vector<uint64_t> ids(counts.size());std::iota(ids.begin(),ids.end(),0);
 k=std::min(k,ids.size());std::partial_sort(ids.begin(),ids.begin()+k,ids.end(),[&](uint64_t a,uint64_t b){return counts[a]!=counts[b]?counts[a]>counts[b]:a<b;});ids.resize(k);return ids;
}
}
