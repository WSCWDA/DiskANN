#pragma once
#include "estimator_scalability.h"
#include <stdexcept>
namespace retbench {
using namespace qshape;
inline void require(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
inline void configure(const std::string& policy,uint64_t ready,uint64_t meta,bool diag){
 require(policy=="none"||policy=="bounded-local"||policy=="lru"||policy=="exact"||policy=="cms","policy");
 config()=Config{};config().enabled=true;config().ready_stats=diag;
 config().retention=(policy=="exact"||policy=="cms")?"frequency":policy;
 config().frequency_mode=policy=="cms"?"cms":"exact";
 config().ready_budget=ready;config().frequency_budget=meta;
 require(ready% (64*4096)==0,"READY budget must be multiple of 256 KiB");
 require(policy!="cms"||(meta>=1024&&meta%1024==0),"CMS budget alignment");
}
inline uint64_t pattern(uint64_t id,size_t word){return Hash::mix(id^Hash::mix(word+1));}
struct Runner {
 Coordinator c;Query q;std::array<uint64_t,512> dst{};
 uint64_t requests=0,hits=0,reads=0,checksum=0,acquire_ns=0,fill_ns=0,publish_ns=0,consume_ns=0;
 bool full,timing;
 Runner(bool f,bool t):full(f),timing(t){}
 void access(uint64_t id){
  current_guard guard(&q);
  ++requests;q.id=requests;
  auto start=timing?now_ns():0;
  auto t=c.acquire({id*4096,4096},q.id,config().inflight_budget,false);
  if(timing)acquire_ns+=now_ns()-start;
  require(bool(t.req),"unexpected allocation/budget bypass");
  require(t.owner!=t.ready_hit,"ticket classification");
  if(t.owner){
   ++reads;start=timing?now_ns():0;
   auto* p=static_cast<uint64_t*>(t.req->data);
   for(size_t i=0;i<512;++i)p[i]=pattern(id,i);
   if(timing)fill_ns+=now_ns()-start;
   start=timing?now_ns():0;c.publish(t.req);if(timing)publish_ns+=now_ns()-start;
  }else ++hits;
  start=timing?now_ns():0;c.consume(t.req,dst.data(),t.owner);if(timing)consume_ns+=now_ns()-start;
  require(dst.front()==pattern(id,0)&&dst.back()==pattern(id,511),"data mismatch");
  if(full)for(size_t i=0;i<512;++i)require(dst[i]==pattern(id,i),"full data mismatch");
  checksum+=dst.front()^dst.back();
 }
 void validate(){
  require(requests==hits+reads,"request conservation");
  require(c.ready_used()%4096==0,"resident alignment");
  require(q.ready_admissions==q.ready_capacity_evictions+c.ready_used()/4096,"resident conservation");
  require(q.ready_ttl_evictions==0,"unexpected TTL");
  require(config().retention=="none"?q.ready_admissions+q.ready_rejects==0:q.ready_admissions+q.ready_rejects==reads,"publication conservation");
  require(c.ready_peak()<=config().ready_budget&&c.inflight_peak()<=config().inflight_budget,"budget");
  require(c.used()==c.ready_used(),"live payload at quiescence");
  require(q.frequency_update_failures==0,"frequency update failure");
  require(q.frequency_updates==(config().retention=="frequency"?requests:0),"frequency update conservation");
  require(q.frequency_gate_checks==q.frequency_gate_accepts+q.frequency_gate_rejects,"gate conservation");
 }
private:
 struct current_guard{Query* prev;explicit current_guard(Query* p):prev(current()){current()=p;}~current_guard(){current()=prev;}};
};
}
