#include "qshape/shared_io_coordinator.h"
#include <cassert>
int main(){
 using namespace qshape;
 FrequencySketch s;s.init(16384,4);assert(s.bytes()==16384);
 assert(s.estimate(0,4096)==0);
 for(int i=0;i<100;++i)s.increment(0,4096);
 assert(s.estimate(0,4096)==100);
 for(uint64_t i=1;i<100000;++i)s.increment(i*4096,4096);
 assert(s.estimate(0,4096)>=100);assert(s.bytes()==16384);
 s.clear();assert(s.estimate(0,4096)==0);
 bool failed=false;try{s.init(1,4);}catch(const std::invalid_argument&){failed=true;}assert(failed);
 config().retention="frequency";config().frequency_mode="cms";config().ready_budget=64*4096;
 Coordinator c;Key a{0,4096},b{4096,4096};while(Hash{}(a)%64!=Hash{}(b)%64)b.offset+=4096;
 auto x=c.acquire(a,0,1<<20);c.publish(x.req);
 auto y=c.acquire(b,1,1<<20);c.publish(y.req);assert(!y.req->retained);
 auto z=c.acquire(b,2,1<<20);c.publish(z.req);assert(z.req->retained);
 assert(c.acquire(b,3,1<<20).ready_hit);c.clear_ready();assert(c.ready_used()==0);
}
