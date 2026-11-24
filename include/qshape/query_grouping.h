#pragma once
#include "baseline.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace qshape {
struct GroupingConfig {
 std::string policy="original", oracle_file;
 uint32_t group_size=64, candidate_pool=256, seed=42;
};
inline GroupingConfig& grouping_config(){ static GroupingConfig c; return c; }
struct GroupingResult { std::vector<uint32_t> order; uint64_t comparisons=0,distance_ns=0,ranking_ns=0,maintenance_ns=0; };
template<class T>
GroupingResult group_queries(const T* data,size_t n,size_t dim,size_t stride,
 const GroupingConfig& c,const std::string& metric) {
 if(n>std::numeric_limits<uint32_t>::max() || !c.group_size || !c.candidate_pool)
  throw std::invalid_argument("invalid grouping size");
 GroupingResult result;
 auto& order=result.order;
 order.resize(n); std::iota(order.begin(),order.end(),0u);
 if(c.policy=="original") return result;
 std::mt19937 rng(c.seed);
 if(c.policy=="random"){std::shuffle(order.begin(),order.end(),rng);return result;}
 if(c.policy=="oracle"){
  std::ifstream in(c.oracle_file);
  std::vector<unsigned char> seen(n,0);
  uint64_t id;
  for(size_t i=0;i<n;++i){
   if(!(in>>id)||id>=n||seen[id]) throw std::runtime_error("invalid oracle permutation");
   seen[id]=1;order[i]=static_cast<uint32_t>(id);
  }
  std::string extra;if(in>>extra) throw std::runtime_error("extra oracle entries");
  return result;
 }
 if(c.policy!="similarity") throw std::invalid_argument("unknown grouping policy");
 std::vector<uint32_t> remaining=order;
 std::vector<double> norms;
 if(metric=="cosine"){
  norms.resize(n);
  for(size_t i=0;i<n;++i){double v=0;for(size_t d=0;d<dim;++d){double x=data[i*stride+d];v+=x*x;}norms[i]=std::sqrt(v);}
 }
 auto score=[&](uint32_t a,uint32_t b){
  double s=0;
  for(size_t d=0;d<dim;++d){
   double x=data[size_t(a)*stride+d],y=data[size_t(b)*stride+d];
   if(metric=="l2"){double z=x-y;s+=z*z;}else s+=x*y;
  }
  if(metric=="cosine") return norms[a]&&norms[b]?-s/(norms[a]*norms[b]):0.0;
  return metric=="l2"?s:-s;
 };
 order.clear();
 while(!remaining.empty()){
  const auto m0=now_ns();
  const auto seed=remaining.front();
  remaining.front()=remaining.back();remaining.pop_back();
  order.push_back(seed);
  const size_t count=std::min<size_t>(c.candidate_pool,remaining.size());
  const size_t take=std::min<size_t>(c.group_size-1,remaining.size());
  if(take>count) throw std::invalid_argument("candidate pool smaller than group_size-1");
  std::vector<std::pair<double,size_t>> ranked;ranked.reserve(count);
  const auto d0=now_ns();result.maintenance_ns+=d0-m0;
  for(size_t j=0;j<count;++j){double s=score(seed,remaining[j]);if(!std::isfinite(s)) throw std::runtime_error("nonfinite query similarity");ranked.emplace_back(s,j);}
  const auto r0=now_ns();result.distance_ns+=r0-d0;
  result.comparisons+=count;
  std::partial_sort(ranked.begin(),ranked.begin()+take,ranked.end());
  std::vector<size_t> erase;erase.reserve(take);
  for(size_t j=0;j<take;++j){auto pos=ranked[j].second;order.push_back(remaining[pos]);erase.push_back(pos);}
  const auto m1=now_ns();result.ranking_ns+=m1-r0;
  std::sort(erase.rbegin(),erase.rend());
  for(auto pos:erase){remaining[pos]=remaining.back();remaining.pop_back();}
  result.maintenance_ns+=now_ns()-m1;
 }
 return result;
}
}
