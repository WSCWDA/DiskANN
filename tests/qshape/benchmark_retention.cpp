#include "retention_benchmark.h"
#include <iostream>
#include <iomanip>
int main(int argc,char** argv){
 using namespace retbench;
 try{
 if(argc!=9)throw std::invalid_argument("policy n ops skew seed ready_bytes metadata_bytes mode");
 std::string policy=argv[1],mode=argv[8];uint64_t n=std::stoull(argv[2]),ops=std::stoull(argv[3]),seed=std::stoull(argv[5]),ready=std::stoull(argv[6]),meta=std::stoull(argv[7]);double skew=std::stod(argv[4]);
 require(ops>0&&ops<=100000000,"ops");require(mode=="correctness"||mode=="perf"||mode=="diag","mode");
 configure(policy,ready,meta,mode!="perf");
 esc::Workload work(n,seed,skew);std::mt19937_64 rng(seed);
 std::vector<uint32_t> input(ops);std::vector<bool> seen(n);uint64_t observed=0,fp=1469598103934665603ULL;
 for(auto& id:input){id=work.next(rng);fp=(fp^id)*1099511628211ULL;if(!seen[id]){seen[id]=true;++observed;}}
 Runner run(mode=="correctness",mode=="diag");
 auto start=now_ns();for(auto id:input)run.access(id);auto elapsed=now_ns()-start;
 run.validate();auto& q=run.q;auto& c=run.c;
 std::cout<<std::setprecision(17)<<"policy,n,ops,skew,seed,ready_budget,meta_budget,mode,observed,fingerprint,checksum,elapsed_ns,hits,reads,admissions,rejects,evictions,unused_evictions,resident,ready_peak,inflight_peak,live_peak,frequency_updates,frequency_failures,counter_bytes,saturations,gate_checks,gate_accepts,gate_rejects,acquire_ns,fill_ns,publish_ns,consume_ns,tracking_ns\n";
 std::cout<<policy<<','<<n<<','<<ops<<','<<skew<<','<<seed<<','<<ready<<','<<meta<<','<<mode<<','<<observed<<','<<fp<<','<<run.checksum<<','<<elapsed<<','<<run.hits<<','<<run.reads<<','<<q.ready_admissions<<','<<q.ready_rejects<<','<<q.ready_capacity_evictions<<','<<q.ready_unused_evictions<<','<<c.ready_used()/4096<<','<<c.ready_peak()<<','<<c.inflight_peak()<<','<<c.peak()<<','<<q.frequency_updates<<','<<q.frequency_update_failures<<','<<q.frequency_counter_bytes<<','<<q.frequency_saturations<<','<<q.frequency_gate_checks<<','<<q.frequency_gate_accepts<<','<<q.frequency_gate_rejects<<','<<run.acquire_ns<<','<<run.fill_ns<<','<<run.publish_ns<<','<<run.consume_ns<<','<<q.frequency_tracking_ns<<'\n';
 c.clear_ready();require(c.used()==0&&c.ready_used()==0,"clear leak");return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
