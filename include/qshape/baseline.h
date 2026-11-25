#pragma once
#include <chrono>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace qshape {
inline uint64_t now_ns() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
struct Config { bool enabled=false, trace=false; std::string sharing="off"; uint64_t inflight_budget=67108864; std::string prefix="qshape"; };
inline Config& config() { static Config c; return c; }
struct Event { uint64_t id, offset, length, time; int64_t result; const char* kind; };
struct Query {
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
 if(config().trace) {
  std::ofstream io(prefix+"_io.csv");
  io<<"query_id,thread_id,request_id,offset,length,event_type,timestamp_ns,result\n";
  for(const auto& q:qs) for(const auto& e:q.events) io<<q.id<<','<<q.thread<<','<<e.id<<','<<e.offset<<','<<e.length<<','<<e.kind<<','<<e.time<<','<<e.result<<'\n';
  if(!io) throw std::runtime_error("QShape IO output failed");
 }
 if(!out||!summary) throw std::runtime_error("QShape output failed");
}
}
