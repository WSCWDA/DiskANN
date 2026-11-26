#pragma once
#include "baseline.h"
#include "frequency_estimator.h"
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
#include <list>
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
struct Budget {
 std::atomic<uint64_t> used{0},peak{0},inflight{0},inflight_peak{0},ready{0},ready_peak{0};
 static bool reserve(std::atomic<uint64_t>& n,uint64_t size,uint64_t limit){
  auto old=n.load();do{if(!size||old>limit||size>limit-old)return false;}while(!n.compare_exchange_weak(old,old+size));return true;
 }
 static void high(std::atomic<uint64_t>& p,uint64_t n){auto old=p.load();while(old<n&&!p.compare_exchange_weak(old,n)){}}
};
struct SharedRequest {
 std::shared_ptr<Budget> budget;
 Key key; void* data=nullptr; uint64_t owner,group=0,life=0;
 std::mutex mu; std::condition_variable cv; bool ready=false,retained=false,independent=false; uint64_t published=0,ready_accesses=0; std::list<Key>::iterator lru_pos,expiry_pos; std::exception_ptr error;
 SharedRequest(std::shared_ptr<Budget> b,Key k,uint64_t o):budget(b),key(k),owner(o){}
 ~SharedRequest(){if(data){std::free(data);budget->used.fetch_sub(key.length);}}
};
class Coordinator {
 // Direct-mapped, bounded history: 1024 entries per shard, no retained payload.
 struct History {Key key{};uint64_t time=0,query=0,group=0;};
 struct Shard {std::mutex mu;std::unordered_map<Key,std::shared_ptr<SharedRequest>,Hash> map;std::unique_ptr<History[]> history; std::unordered_map<Key,uint64_t,Hash> frequencies; FrequencySketch sketch; std::list<Key> lru,expiry; uint64_t ready_bytes=0;};
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
 static void record(const SharedRequest& p,const char* kind) noexcept {
  if(config().region_trace)if(auto* q=current())q->region(p.key.offset,p.key.length,kind,p.owner,p.life);
 }
 static bool ttl(){return config().retention=="ttl"||config().retention=="ttl-lru";}
 static bool frequency(){return config().retention=="frequency";}
 static bool lru(){return config().retention=="lru"||config().retention=="ttl-lru"||frequency();}
 static bool cms(){return config().frequency_mode=="cms";}
 static uint64_t count(const Shard& sh,Key k){if(cms())return sh.sketch.estimate(k.offset,k.length);auto i=sh.frequencies.find(k);return i==sh.frequencies.end()?0:i->second;}
 static bool dynamic(){return ttl()||lru();}
 static bool expired(const SharedRequest& p,uint64_t now){return ttl()&&(now-p.published)/1000>=config().ready_ttl_us;}
 // All list/map operations under the owning shard lock. No cross-shard locking.
 void evict(Shard& sh,Key k,bool time,uint64_t now){
  auto it=sh.map.find(k);auto& p=*it->second;
  if(auto* q=current()){if(time)++q->ready_ttl_evictions;else ++q->ready_capacity_evictions;
   if(config().ready_stats){q->ready_unused_evictions+=p.ready_accesses==0;q->ready_eviction_age_ns+=now-p.published;}}
  record(p,time?"EVICT_TTL":"EVICT_CAPACITY");
  sh.lru.erase(p.lru_pos);sh.expiry.erase(p.expiry_pos);
  sh.ready_bytes-=k.length;budget->ready.fetch_sub(k.length);sh.map.erase(it);
 }
 void purge(Shard& sh,uint64_t now){
  while(ttl()&&!sh.expiry.empty()){
   auto k=sh.expiry.front();if(!expired(*sh.map.at(k),now))break;evict(sh,k,true,now);
  }
 }
 bool admit(Shard& sh,const std::shared_ptr<SharedRequest>& p){
  if(!dynamic()&&config().retention!="bounded-local")return Budget::reserve(budget->ready,p->key.length,config().ready_budget);
  const auto now=now_ns();p->published=now;purge(sh,now);
  const auto cap=config().ready_budget/64+(shard_id(p->key)<config().ready_budget%64?1:0);
  if(p->key.length>cap)return false;
  // Plan all victims before changing the cache. Allocate list nodes before eviction.
  if(frequency()){
   uint64_t remaining=sh.ready_bytes;
   const bool gate=remaining>cap-p->key.length;
   auto* q=current(); if(gate&&q)++q->frequency_gate_checks;
   for(auto it=sh.lru.begin();remaining>cap-p->key.length&&it!=sh.lru.end();++it){
    if(count(sh,p->key)<=count(sh,*it)){if(q)++q->frequency_gate_rejects;return false;}
    remaining-=it->length;
   }
   if(remaining>cap-p->key.length){if(gate&&q)++q->frequency_gate_rejects;return false;}
   if(gate&&q)++q->frequency_gate_accepts;
   try{sh.lru.push_back(p->key);try{sh.expiry.push_back(p->key);}catch(...){sh.lru.pop_back();return false;}}catch(...){return false;}
   while(sh.ready_bytes>cap-p->key.length)evict(sh,sh.lru.front(),false,now);
   if(!Budget::reserve(budget->ready,p->key.length,config().ready_budget)){sh.lru.pop_back();sh.expiry.pop_back();return false;}
   p->lru_pos=std::prev(sh.lru.end());p->expiry_pos=std::prev(sh.expiry.end());sh.ready_bytes+=p->key.length;return true;
  }
  while(lru()&&sh.ready_bytes>cap-p->key.length&&!sh.lru.empty())evict(sh,sh.lru.front(),false,now);
  if(sh.ready_bytes>cap-p->key.length)return false;
  // Allocation failure rejects retention without preventing I/O publication.
  try{sh.lru.push_back(p->key);try{sh.expiry.push_back(p->key);}catch(...){sh.lru.pop_back();return false;}}catch(...){return false;}
  if(!Budget::reserve(budget->ready,p->key.length,config().ready_budget)){sh.lru.pop_back();sh.expiry.pop_back();return false;}
  p->lru_pos=std::prev(sh.lru.end());p->expiry_pos=std::prev(sh.expiry.end());sh.ready_bytes+=p->key.length;return true;
 }
public:
 Coordinator(){if(frequency()&&cms()){for(auto& sh:shards)sh.sketch.init(config().frequency_budget/64,config().frequency_depth);}}
 struct Ticket {std::shared_ptr<SharedRequest> req;bool owner=false;bool ready_hit=false;};
 uint64_t used()const{return budget->used.load();}
 uint64_t peak()const{return budget->peak.load();}
 uint64_t ready_used()const{return budget->ready.load();}
 uint64_t ready_peak()const{return budget->ready_peak.load();}
 uint64_t inflight_peak()const{return budget->inflight_peak.load();}
 // Only at quiescent file lifecycle boundaries; outstanding tickets remain valid.
 void clear_ready(){
  for(auto& sh:shards){std::lock_guard<std::mutex> lock(sh.mu);
   for(auto it=sh.map.begin();it!=sh.map.end();){
    if(!it->second->retained){++it;continue;}
    budget->ready.fetch_sub(it->first.length);it=sh.map.erase(it);
   }
   sh.history.reset();sh.frequencies.clear();sh.frequencies.rehash(0);sh.sketch.clear();sh.lru.clear();sh.expiry.clear();sh.ready_bytes=0;
  }
 }
 Ticket acquire(Key k,uint64_t qid,uint64_t limit,bool share=true){
  auto& sh=shard(k);auto* st=stats(k);TimedLock lock(sh.mu,st);if(st)++st->lookups;
  auto* diag=config().ready_stats?current():nullptr;
  const auto begin=diag?now_ns():0;
  if(frequency()){
   auto* q=current();const auto t=diag?now_ns():0;
   if(cms()){auto n=sh.sketch.increment(k.offset,k.length);if(q){++q->frequency_updates;q->frequency_saturations+=n;q->frequency_counter_bytes=64*sh.sketch.bytes();}}
   else try{auto& n=sh.frequencies[k];if(n!=UINT64_MAX)++n;if(q){++q->frequency_updates;q->frequency_shard_entries=std::max(q->frequency_shard_entries,static_cast<uint64_t>(sh.frequencies.size()));}}
   catch(const std::bad_alloc&){if(q)++q->frequency_update_failures;}
   if(diag)diag->frequency_tracking_ns+=now_ns()-t;
  }
  if(ttl())purge(sh,now_ns());
  auto it=sh.map.find(k);if(it!=sh.map.end()&&(share||it->second->retained)){
   auto& p=*it->second;
   if(p.retained){
    if(lru())sh.lru.splice(sh.lru.end(),sh.lru,p.lru_pos);
    if(diag){++p.ready_accesses;diag->ready_hit_age_ns+=now_ns()-p.published;
     if(p.owner!=qid){++diag->ready_cross_query_hits;if(p.group==diag->group_id)++diag->ready_same_group_hits;else ++diag->ready_cross_group_hits;}}
   }
   if(diag)diag->ready_retention_ns+=now_ns()-begin;
   record(p,p.retained?"READY_HIT":"INFLIGHT_JOIN");
   if(st)++st->joins;return {it->second,false,p.retained};
  }
  if(diag)diag->ready_retention_ns+=now_ns()-begin;
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
  p->independent=!share;
  const auto extra=config().retention!="none"?config().ready_budget:0;
  if(extra>UINT64_MAX-limit)return {};
  if(!Budget::reserve(budget->inflight,k.length,limit))return {};
  if(!Budget::reserve(budget->used,k.length,limit+extra)){budget->inflight.fetch_sub(k.length);return {};}
  Budget::high(budget->peak,budget->used.load());
  Budget::high(budget->inflight_peak,budget->inflight.load());
  if(posix_memalign(&p->data,4096,k.length)!=0){p->data=nullptr;budget->used.fetch_sub(k.length);budget->inflight.fetch_sub(k.length);return {};}
  try{if(share)sh.map.emplace(k,p);}catch(...){budget->inflight.fetch_sub(k.length);throw;}
  if(config().region_trace&&q)p->life=++q->region_next;
  record(*p,"OWNER");
  if(st)++st->owners;return {p,true};
 }
 void publish(const std::shared_ptr<SharedRequest>& p,std::exception_ptr error={}){
  auto& sh=shard(p->key);
  {auto* st=stats(p->key);TimedLock lock(sh.mu,st);if(st)++st->publishes;std::lock_guard<std::mutex> state(p->mu);
   auto it=sh.map.find(p->key);
   if(!p->independent&&(it==sh.map.end()||it->second!=p))std::terminate();
   if(p->independent&&!error&&config().retention!="none"){
    if(ttl())purge(sh,now_ns());
    // Independent misses never register until completion. First successful admission wins.
    try{auto inserted=sh.map.emplace(p->key,p);it=inserted.first;}catch(...){it=sh.map.end();}
   }
   const bool registered=it!=sh.map.end()&&it->second==p;
   p->error=error;p->ready=true;
   record(*p,error?"PUBLISH_ERROR":"PUBLISH");
   if(!error&&config().retention!="none"){
    auto* diag=config().ready_stats?current():nullptr;const auto begin=diag?now_ns():0;
    p->published=now_ns();p->retained=registered&&admit(sh,p);
    if(diag)diag->ready_retention_ns+=now_ns()-begin;
    record(*p,p->retained?"ADMIT":"REJECT");
    if(p->retained){Budget::high(budget->ready_peak,budget->ready.load());if(auto* q=current())++q->ready_admissions;}
    else if(auto* q=current())++q->ready_rejects;
   }
   budget->inflight.fetch_sub(p->key.length);
   if(registered&&!p->retained)sh.map.erase(it);
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
