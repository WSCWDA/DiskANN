#include "estimator_scalability.h"
#include <iostream>
#include <iomanip>
#include <sys/resource.h>
int main(int argc,char** argv){
 using namespace esc;
 if(argc!=10){std::cerr<<"mode backend cardinality accesses budget skew threads seed cover\n";return 2;}
 std::string mode=argv[1],backend=argv[2];uint64_t n=std::stoull(argv[3]),ops=std::stoull(argv[4]),budget=std::stoull(argv[5]),threads=std::stoull(argv[7]),seed=std::stoull(argv[8]);double skew=std::stod(argv[6]);bool cover=std::stoi(argv[9])!=0;
 if(!ops||!threads||threads>64||(backend!="cms"&&backend!="exact")||(mode!="update"&&mode!="estimate"&&mode!="mixed"&&mode!="diagnostic")||(mode=="diagnostic"&&threads!=1)||(cover&&ops<n))return 2;
 Workload work(n,seed,skew);Estimator est(backend=="cms",budget);
 // Generate identical per-thread streams outside the timed region, in bounded chunks.
 // Full input is retained for timing isolation; RSS includes this input.
 std::vector<uint32_t> input(ops);std::mt19937_64 rng(seed);
 uint64_t fingerprint=1469598103934665603ULL;
 for(uint64_t i=0;i<ops;++i){input[i]=cover&&i<n?i:work.next(rng);fingerprint=(fingerprint^input[i])*1099511628211ULL;}
 uint64_t sat=0,checksum=0,elapsed=0;
 if(mode=="estimate")for(auto id:input)est.apply(id,true,0,sat);
 if(mode=="diagnostic"){for(auto id:input)est.apply(id,true,0,sat);}
 else{
  std::vector<uint64_t> sums(threads),sats(threads);std::vector<std::thread> workers;std::atomic<unsigned> ready{0};std::atomic<bool> go{false};
  for(unsigned t=0;t<threads;++t)workers.emplace_back([&,t]{++ready;while(!go.load(std::memory_order_acquire))std::this_thread::yield();for(uint64_t i=ops*t/threads;i<ops*(t+1)/threads;++i)sums[t]+=est.apply(input[i],mode!="estimate",mode=="update"?0:mode=="mixed"?2:1,sats[t]);});
  while(ready.load()!=threads)std::this_thread::yield();auto start=now_ns();go.store(true,std::memory_order_release);for(auto& t:workers)t.join();elapsed=now_ns()-start;
  for(auto x:sums)checksum+=x;for(auto x:sats)sat+=x;
 }
 struct rusage usage{};getrusage(RUSAGE_SELF,&usage);
 std::cout<<std::setprecision(17)<<"mode,backend,n,ops,budget,skew,threads,seed,cover,fingerprint,elapsed_ns,payload_bytes,exact_entries,saturations,checksum,rss_kib,observed,under,zero,mae,k,hot_recall,utility_coverage\n";
 auto prefix=[&]{std::cout<<mode<<','<<backend<<','<<n<<','<<ops<<','<<budget<<','<<skew<<','<<threads<<','<<seed<<','<<cover<<','<<fingerprint<<','<<elapsed<<','<<est.bytes()<<','<<est.entries()<<','<<sat<<','<<checksum<<','<<usage.ru_maxrss;};
 if(mode!="diagnostic"){prefix();std::cout<<",0,0,0,0,0,0,0\n";return 0;}
 std::vector<uint64_t> truth(n),estimate(n);for(auto id:input)++truth[id];
 uint64_t observed=0,under=0,zero=0,dummy=0;long double error=0;
 for(uint64_t i=0;i<n;++i){estimate[i]=est.apply(i,false,1,dummy);if(truth[i]){++observed;under+=estimate[i]<truth[i];zero+=estimate[i]==truth[i];error+=std::abs((long double)estimate[i]-truth[i]);}}
 for(size_t k:{1024,4096,16384}){
  auto a=top(truth,k),b=top(estimate,k);uint64_t av=0,bv=0,overlap=0;for(auto i:a)av+=truth[i];for(auto i:b)bv+=truth[i];std::sort(a.begin(),a.end());for(auto i:b)overlap+=std::binary_search(a.begin(),a.end(),i);
  prefix();std::cout<<','<<observed<<','<<under<<','<<zero<<','<<double(error/observed)<<','<<a.size()<<','<<double(overlap)/a.size()<<','<<double(bv)/av<<'\n';
 }
}
