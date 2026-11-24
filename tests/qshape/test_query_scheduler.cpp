#include "qshape/query_scheduler.h"
#include <atomic>
#include <thread>
#include <cassert>
int main(){
 for(size_t n:{0u,1u,65u,10000u})for(size_t g:{1u,32u,128u})for(size_t w:{1u,4u}){
  qshape::GroupScheduler s(n,g,w);std::vector<std::atomic<int>> seen(n);
  for(auto& v:seen)v.store(0);
  std::vector<std::thread> workers;
  for(int i=0;i<16;++i)workers.emplace_back([&]{for(;;){auto p=s.take();if(p==s.none())break;assert(p<n);++seen[p];std::this_thread::yield();s.done(p/g);}});
  for(auto& t:workers)t.join();for(auto& v:seen)assert(v.load()==1);
 }
}
