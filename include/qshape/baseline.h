#pragma once
#include <chrono>
#include <array>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace qshape {
inline uint64_t now_ns() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
struct Config { bool enabled=false, trace=false; std::string sharing="off", hash_policy="mixed"; bool shard_stats=false, breakdown=false, reuse_stats=false; uint64_t inflight_budget=67108864; std::string prefix="qshape"; };
inline Config& config() { static Config c; return c; }
struct Event { uint64_t id, offset, length, time; int64_t result; const char* kind; };
struct ShardStats {uint64_t lookups=0,owners=0,joins=0,publishes=0,wait_ns=0,hold_ns=0;};
struct ReuseSample {uint64_t gap,offset,length,previous_query,previous_group;};
struct Query {
 uint64_t owner_io_ns=0,publish_ns=0,owner_wait_ns=0,consumer_wait_ns=0,owner_copy_ns=0,consumer_copy_ns=0,copy_bytes=0,owner_consumes=0,consumer_consumes=0,ready_before_wait_count=0,blocking_wait_count=0,reuse_lookups=0,reuse_hits=0,reuse_cross_query=0,reuse_same_group=0,reuse_evictions=0;
 std::vector<ReuseSample> reuse;
 std::array<ShardStats,64> shards{};
 uint64_t execution_id=0,group_id=0,dispatch_ns=0,scheduler_ns=0;
 uint64_t id=0,start=0,end=0,submitted=0,bytes=0,completed=0,errors=0,logical=0,hits=0,next=0;
 uint64_t reader_requests=0,reader_bytes=0,shared_hits=0,shared_bytes=0,same_query_hits=0,bypass=0,lookup_ns=0,wait_copy_ns=0,peak_shared_bytes=0;
 int thread=0;
 std::vector<Event> events;
 void event(uint64_t id_,uint64_t off,uint64_t len,const char* kind,int64_t result,uint64_t time) {
  if(config().trace) events.push_back({id_,off,len,time,result,kind});
 }
};
inline Query*& current() { static thread_local Query* q=nullptr; return q; }
struct Scope {
 Query* previous;
 explicit Scope(Query* q):previous(current()) { current()=q; if(q) q->start=now_ns(); }
 ~Scope() { if(current()) current()->end=now_ns(); current()=previous; }
};
inline void write(const std::vector<Query>& qs,const std::string& prefix,uint64_t arrival,uint64_t finish) {
 std::ofstream out(prefix+"_queries.csv"), summary(prefix+"_summary.csv");
 out<<"query_id,execution_id,group_id,thread_id,arrival_ns,search_start_ns,search_end_ns,logical_node_reads,static_cache_hits,submitted_reads,submitted_bytes,completed_reads,completion_errors,dispatch_ns,scheduler_ns,reader_requests,reader_bytes,shared_hits,shared_bytes,same_query_hits,bypass,lookup_ns,wait_copy_ns,peak_shared_bytes\n";
 uint64_t reads=0,bytes=0,errors=0,logical=0,hits=0;
 for(const auto& q:qs) {
  out<<q.id<<','<<q.execution_id<<','<<q.group_id<<','<<q.thread<<','<<arrival<<','<<q.start<<','<<q.end<<','<<q.logical<<','<<q.hits<<','<<q.submitted<<','<<q.bytes<<','<<q.completed<<','<<q.errors<<','<<q.dispatch_ns<<','<<q.scheduler_ns<<','<<q.reader_requests<<','<<q.reader_bytes<<','<<q.shared_hits<<','<<q.shared_bytes<<','<<q.same_query_hits<<','<<q.bypass<<','<<q.lookup_ns<<','<<q.wait_copy_ns<<','<<q.peak_shared_bytes<<'\n';
  reads+=q.submitted;bytes+=q.bytes;errors+=q.errors;logical+=q.logical;hits+=q.hits;
 }
 summary<<"queries,elapsed_ns,logical_node_reads,static_cache_hits,submitted_reads,submitted_bytes,completion_errors\n"<<qs.size()<<','<<finish-arrival<<','<<logical<<','<<hits<<','<<reads<<','<<bytes<<','<<errors<<'\n';
 if(config().breakdown||config().reuse_stats){
  std::ofstream d(prefix+"_diagnostics.csv");
  d<<"query_id,owner_io_ns,publish_ns,owner_wait_ns,consumer_wait_ns,owner_copy_ns,consumer_copy_ns,copy_bytes,owner_consumes,consumer_consumes,ready_before_wait_count,blocking_wait_count,reuse_lookups,reuse_hits,reuse_cross_query,reuse_same_group,reuse_evictions\n";
  for(const auto& q:qs)d<<q.id<<','<<q.owner_io_ns<<','<<q.publish_ns<<','<<q.owner_wait_ns<<','<<q.consumer_wait_ns<<','<<q.owner_copy_ns<<','<<q.consumer_copy_ns<<','<<q.copy_bytes<<','<<q.owner_consumes<<','<<q.consumer_consumes<<','<<q.ready_before_wait_count<<','<<q.blocking_wait_count<<','<<q.reuse_lookups<<','<<q.reuse_hits<<','<<q.reuse_cross_query<<','<<q.reuse_same_group<<','<<q.reuse_evictions<<'\n';
  if(!d)throw std::runtime_error("diagnostics output failed");
 }
 if(config().reuse_stats){
  std::ofstream f(prefix+"_reuse.csv");
  f<<"query_id,group_id,offset,length,previous_query,previous_group,gap_ns\n";
  for(const auto& q:qs)for(const auto& x:q.reuse)f<<q.id<<','<<q.group_id<<','<<x.offset<<','<<x.length<<','<<x.previous_query<<','<<x.previous_group<<','<<x.gap<<'\n';
  if(!f)throw std::runtime_error("reuse output failed");
 }
 if(config().shard_stats){
  std::ofstream shard(prefix+"_shards.csv");
  shard<<"shard_id,lookups,owners,joins,publishes,lock_wait_ns,lock_hold_ns\n";
  for(size_t i=0;i<64;++i){
   ShardStats t;
   for(const auto& q:qs){const auto& s=q.shards[i];t.lookups+=s.lookups;t.owners+=s.owners;t.joins+=s.joins;t.publishes+=s.publishes;t.wait_ns+=s.wait_ns;t.hold_ns+=s.hold_ns;}
   shard<<i<<','<<t.lookups<<','<<t.owners<<','<<t.joins<<','<<t.publishes<<','<<t.wait_ns<<','<<t.hold_ns<<'\n';
  }
  if(!shard)throw std::runtime_error("shard output failed");
 }
 if(config().trace) {
  std::ofstream io(prefix+"_io.csv");
  io<<"query_id,thread_id,request_id,offset,length,event_type,timestamp_ns,result\n";
  for(const auto& q:qs) for(const auto& e:q.events) io<<q.id<<','<<q.thread<<','<<e.id<<','<<e.offset<<','<<e.length<<','<<e.kind<<','<<e.time<<','<<e.result<<'\n';
  if(!io) throw std::runtime_error("QShape IO output failed");
 }
 if(!out||!summary) throw std::runtime_error("QShape output failed");
}
}
