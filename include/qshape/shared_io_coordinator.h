#pragma once
#include "baseline.h"
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <algorithm>
namespace qshape {
struct Key {uint64_t offset,length; bool operator==(const Key& k)const{return offset==k.offset&&length==k.length;}};
struct Hash {size_t operator()(const Key& k)const{return std::hash<uint64_t>{}(k.offset)^(std::hash<uint64_t>{}(k.length)<<1);}};
struct Budget {std::atomic<uint64_t> used{0},peak{0};};
struct SharedRequest {
 std::shared_ptr<Budget> budget;
 Key key; void* data=nullptr; uint64_t owner;
 std::mutex mu; std::condition_variable cv; bool ready=false; std::exception_ptr error;
 SharedRequest(std::shared_ptr<Budget> b,Key k,uint64_t o):budget(b),key(k),owner(o){}
 ~SharedRequest(){if(data){std::free(data);budget->used.fetch_sub(key.length);}}
};
class Coordinator {
 struct Shard {std::mutex mu;std::unordered_map<Key,std::shared_ptr<SharedRequest>,Hash> map;};
 std::array<Shard,64> shards;
 std::shared_ptr<Budget> budget=std::make_shared<Budget>();
 Shard& shard(Key k){return shards[Hash{}(k)%shards.size()];}
public:
 struct Ticket {std::shared_ptr<SharedRequest> req;bool owner=false;};
 uint64_t used()const{return budget->used.load();}
 uint64_t peak()const{return budget->peak.load();}
 Ticket acquire(Key k,uint64_t qid,uint64_t limit){
  auto& sh=shard(k);std::lock_guard<std::mutex> lock(sh.mu);
  auto it=sh.map.find(k);if(it!=sh.map.end())return {it->second,false};
  auto p=std::make_shared<SharedRequest>(budget,k,qid);
  auto old=budget->used.load();
  do {if(!k.length||old>limit||k.length>limit-old)return {};}while(!budget->used.compare_exchange_weak(old,old+k.length));
  if(posix_memalign(&p->data,4096,k.length)!=0){p->data=nullptr;budget->used.fetch_sub(k.length);return {};}
  auto peak=budget->peak.load();while(peak<old+k.length&&!budget->peak.compare_exchange_weak(peak,old+k.length)){}
  sh.map.emplace(k,p);return {p,true};
 }
 void publish(const std::shared_ptr<SharedRequest>& p,std::exception_ptr error={}){
  auto& sh=shard(p->key);
  {std::lock_guard<std::mutex> lock(sh.mu);std::lock_guard<std::mutex> state(p->mu);
   auto it=sh.map.find(p->key);if(it==sh.map.end()||it->second!=p)std::terminate();
   p->error=error;p->ready=true;sh.map.erase(it);}
  p->cv.notify_all();
 }
 void consume(const std::shared_ptr<SharedRequest>& p,void* dst){
  {std::unique_lock<std::mutex> lock(p->mu);p->cv.wait(lock,[&]{return p->ready;});if(p->error)std::rethrow_exception(p->error);}
  std::memcpy(dst,p->data,p->key.length);
 }
};
}
