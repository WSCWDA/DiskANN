#pragma once
#include "baseline.h"
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <memory>
#include <new>
#include <mutex>
#include <unordered_map>
#include <algorithm>
namespace qshape {
struct Key {uint64_t offset,length; bool operator==(const Key& k)const{return offset==k.offset&&length==k.length;}};
struct Hash {
 static uint64_t mix(uint64_t x) noexcept {
  x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL;
  x ^= x >> 27; x *= 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
 }
 size_t operator()(const Key& k) const noexcept {
  if(config().hash_policy=="legacy") return std::hash<uint64_t>{}(k.offset)^(std::hash<uint64_t>{}(k.length)<<1);
  return static_cast<size_t>(mix(k.offset)^mix(k.length+0x9e3779b97f4a7c15ULL));
 }
};
struct Budget {std::atomic<uint64_t> used{0},peak{0};};
struct SharedRequest {
 std::shared_ptr<Budget> budget;
 Key key; void* data=nullptr; uint64_t owner,group=0;
 std::mutex mu; std::condition_variable cv; bool ready=false; std::exception_ptr error;
 SharedRequest(std::shared_ptr<Budget> b,Key k,uint64_t o):budget(b),key(k),owner(o){}
 ~SharedRequest(){if(data){std::free(data);budget->used.fetch_sub(key.length);}}
};
class Coordinator {
 // Direct-mapped, bounded history: 1024 entries per shard, no retained payload.
 struct History {Key key{};uint64_t time=0,query=0,group=0;};
 struct Shard {std::mutex mu;std::unordered_map<Key,std::shared_ptr<SharedRequest>,Hash> map;std::unique_ptr<History[]> history;};
 static size_t history_slot(Key k){return (Hash{}(k)>>6)%1024;}
 std::array<Shard,64> shards;
 std::shared_ptr<Budget> budget=std::make_shared<Budget>();
 static size_t shard_id(Key k){return Hash{}(k)%64;}
 Shard& shard(Key k){return shards[shard_id(k)];}
 // Per-query counters avoid introducing another contended shared counter.
 struct TimedLock {
  std::unique_lock<std::mutex> lock;
  ShardStats* stats;
  uint64_t acquired=0;
  TimedLock(std::mutex& mu,ShardStats* s):lock(mu,std::defer_lock),stats(s){
   const auto start=stats?now_ns():0;
   lock.lock();
   if(stats){acquired=now_ns();stats->wait_ns+=acquired-start;}
  }
  ~TimedLock(){if(stats)stats->hold_ns+=now_ns()-acquired;}
 };
 static ShardStats* stats(Key k){
  auto* q=current();return q&&config().shard_stats?&q->shards[shard_id(k)]:nullptr;
 }
public:
 struct Ticket {std::shared_ptr<SharedRequest> req;bool owner=false;};
 uint64_t used()const{return budget->used.load();}
 uint64_t peak()const{return budget->peak.load();}
 Ticket acquire(Key k,uint64_t qid,uint64_t limit){
  auto& sh=shard(k);auto* st=stats(k);TimedLock lock(sh.mu,st);if(st)++st->lookups;
  auto it=sh.map.find(k);if(it!=sh.map.end()){if(st)++st->joins;return {it->second,false};}
  auto* q=current();
  if(q&&config().reuse_stats){
   ++q->reuse_lookups;
   if(sh.history){
    const auto& e=sh.history[history_slot(k)];
    if(e.time&&e.key==k){
     const auto gap=now_ns()-e.time;
     ++q->reuse_hits;
     if(e.query!=qid){++q->reuse_cross_query;if(e.group==q->group_id)++q->reuse_same_group;}
     // Cap per-query samples; counters remain complete.
     if(q->reuse.size()<4096)q->reuse.push_back({gap,k.offset,k.length,e.query,e.group});
    }
   }
  }
  auto p=std::make_shared<SharedRequest>(budget,k,qid);
  if(q)p->group=q->group_id;
  auto old=budget->used.load();
  do {if(!k.length||old>limit||k.length>limit-old)return {};}while(!budget->used.compare_exchange_weak(old,old+k.length));
  if(posix_memalign(&p->data,4096,k.length)!=0){p->data=nullptr;budget->used.fetch_sub(k.length);return {};}
  auto peak=budget->peak.load();while(peak<old+k.length&&!budget->peak.compare_exchange_weak(peak,old+k.length)){}
  sh.map.emplace(k,p);if(st)++st->owners;return {p,true};
 }
 void publish(const std::shared_ptr<SharedRequest>& p,std::exception_ptr error={}){
  auto& sh=shard(p->key);
  {auto* st=stats(p->key);TimedLock lock(sh.mu,st);if(st)++st->publishes;std::lock_guard<std::mutex> state(p->mu);
   auto it=sh.map.find(p->key);if(it==sh.map.end()||it->second!=p)std::terminate();
   p->error=error;p->ready=true;sh.map.erase(it);
   if(!error&&config().reuse_stats){
    // Diagnostic allocation must never prevent notification.
    if(!sh.history)sh.history.reset(new(std::nothrow) History[1024]);
    if(sh.history){
     auto& e=sh.history[history_slot(p->key)];
     if(auto* q=current())if(e.time&&!(e.key==p->key))++q->reuse_evictions;
     e={p->key,now_ns(),p->owner,p->group};
    }
   }
  }
  p->cv.notify_all();
 }
 void consume(const std::shared_ptr<SharedRequest>& p,void* dst,bool owner=false){
  auto* q=config().breakdown?current():nullptr;
  const auto start=q?now_ns():0;
  {std::unique_lock<std::mutex> lock(p->mu);
   if(q&&!owner){if(p->ready)++q->ready_before_wait_count;else ++q->blocking_wait_count;}
   p->cv.wait(lock,[&]{return p->ready;});if(p->error)std::rethrow_exception(p->error);}
  const auto copy_start=q?now_ns():0;
  std::memcpy(dst,p->data,p->key.length);
  if(q){
   const auto end=now_ns();
   if(owner){++q->owner_consumes;q->owner_wait_ns+=copy_start-start;q->owner_copy_ns+=end-copy_start;}
   else{++q->consumer_consumes;q->consumer_wait_ns+=copy_start-start;q->consumer_copy_ns+=end-copy_start;}
   q->copy_bytes+=p->key.length;
  }
 }
};
}
