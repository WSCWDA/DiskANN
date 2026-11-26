#include "retention_benchmark.h"
int main(){
 using namespace retbench;
 uint64_t b=1;while(Hash{}({0,4096})%64!=Hash{}({b*4096,4096})%64)++b;
 for(std::string p:{"none","bounded-local","lru","exact","cms"}){
  configure(p,64*4096,524288,true);Runner r(true,true);
  for(auto id:std::vector<uint64_t>{0,0,b,b,b,0})r.access(id);
  r.validate();
  require(r.hits==(p=="none"?0:p=="bounded-local"?2:p=="lru"?3:1),"expected hits");
  r.c.clear_ready();require(r.c.used()==0,"clear");
  r.access(0);require(r.reads+r.hits==7,"reset access");r.c.clear_ready();
 }
 configure("lru",64*4096,0,true);Coordinator c;
 auto x=c.acquire({0,4096},0,4096,false);require(x.owner,"owner");
 auto fail=c.acquire({b*4096,4096},1,4096,false);require(!fail.req,"budget bypass");
 c.publish(x.req);auto y=c.acquire({b*4096,4096},1,4096,false);c.publish(y.req);
 require(c.used()==8192&&c.ready_used()==4096,"pinned eviction");
 x.req.reset();y.req.reset();c.clear_ready();require(c.used()==0,"release");
}
