#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <vector>
int main(){
 using namespace qshape;
 config().hash_policy="mixed";config().ready_budget=64*4096;
 Key a{0,4096},b{4096,4096},d{8192,4096};
 while(Hash{}(b)%64!=Hash{}(a)%64)b.offset+=4096;
 while(Hash{}(d)%64==Hash{}(a)%64)d.offset+=4096;
 for(bool share:{false,true})for(const char* policy:{"bounded","bounded-local","lru"}){
  config().retention=policy;Coordinator c;
  auto x=c.acquire(a,0,65536,share);assert(x.owner);c.publish(x.req);
  auto y=c.acquire(b,1,65536,share);assert(y.owner);c.publish(y.req);
  auto z=c.acquire(d,2,65536,share);assert(z.owner);c.publish(z.req);
  bool global=config().retention=="bounded",local=config().retention=="bounded-local";
  assert(c.ready_used()==(global?3:2)*4096);
  auto hit=c.acquire(local?a:b,3,65536,share);assert(hit.ready_hit&&!hit.owner);
  auto probe=c.acquire(local?b:a,4,65536,share);
  assert(probe.ready_hit==global);if(probe.owner)c.publish(probe.req);
  c.clear_ready();assert(c.ready_used()==0);
  x={};y={};z={};hit={};probe={};assert(c.used()==0);
 }
}
