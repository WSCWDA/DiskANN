#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <thread>
int main(){
 using namespace qshape;config().ready_budget=64*8192;config().ready_stats=true;
 Key a{0,4096},b{4096,4096},c{8192,4096};
 // Find three distinct keys on the same shard.
 while(Hash{}(b)%64!=Hash{}(a)%64)b.offset+=4096;
 c.offset=b.offset+4096;while(Hash{}(c)%64!=Hash{}(a)%64)c.offset+=4096;
 for(auto policy:{"lru","ttl","ttl-lru"}){
  config().retention=policy;config().ready_ttl_us=1000000;Coordinator co;
  Query q;Scope scope(&q);
  auto x=co.acquire(a,1,65536);assert(x.owner);std::memset(x.req->data,9,4096);co.publish(x.req);
  auto y=co.acquire(b,2,65536);assert(y.owner);co.publish(y.req);
  auto h=co.acquire(a,3,65536);assert(h.ready_hit);
  auto z=co.acquire(c,4,65536);assert(z.owner);co.publish(z.req);
  assert(co.ready_used()==8192);
  if(config().retention!="ttl"){assert(q.ready_capacity_evictions==1);auto miss=co.acquire(b,5,65536);assert(miss.owner);co.publish(miss.req);}
  else assert(q.ready_rejects==1);
  char buf[4096];co.consume(h.req,buf);assert(buf[0]==9);
  co.clear_ready();assert(co.ready_used()==0);
 }
 config().retention="ttl";config().ready_ttl_us=1000;Coordinator co;
 auto x=co.acquire(a,1,65536);co.publish(x.req);
 std::this_thread::sleep_for(std::chrono::milliseconds(5));
 auto y=co.acquire(a,2,65536);assert(y.owner);co.publish(y.req);
}
