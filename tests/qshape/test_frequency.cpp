#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <vector>
int main(){
 using namespace qshape;
 config().retention="frequency";config().ready_budget=64*4096;
 Coordinator c; Key a{0,4096},b{4096,4096};
 while(Hash{}(a)%64!=Hash{}(b)%64)b.offset+=4096;
 auto x=c.acquire(a,0,1<<20);assert(x.owner);c.publish(x.req);
 auto y=c.acquire(b,1,1<<20);assert(y.owner);c.publish(y.req);assert(!y.req->retained);
 auto z=c.acquire(b,2,1<<20);assert(z.owner);
 auto j=c.acquire(b,3,1<<20);assert(!j.owner&&!j.ready_hit);
 c.publish(z.req);assert(z.req->retained);
 assert(c.acquire(b,4,1<<20).ready_hit);
 assert(c.ready_used()==4096);
 c.clear_ready();assert(c.ready_used()==0);
 auto p=c.acquire(a,5,1<<20);c.publish(p.req);assert(p.req->retained);
 auto t=c.acquire(b,6,1<<20);c.publish(t.req);assert(!t.req->retained);
}
