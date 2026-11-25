#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <thread>
int main(){
 using namespace qshape;
 config().retention="bounded";config().ready_budget=4096;
 Coordinator c; Key a{0,4096},b{4096,4096};
 auto x=c.acquire(a,1,4096);assert(x.owner);
 auto j=c.acquire(a,2,4096);assert(!j.owner&&!j.ready_hit);
 std::memset(x.req->data,7,4096);c.publish(x.req);
 auto h=c.acquire(a,3,4096);assert(h.ready_hit&&!h.owner);
 std::thread t([&]{char buf[4096];c.consume(h.req,buf);for(char v:buf)assert(v==7);});t.join();
 auto y=c.acquire(b,4,4096);assert(y.owner);c.publish(y.req);
 assert(c.ready_used()==4096&&c.used()==8192);
 assert(!c.acquire({8192,4096},5,4096).req);
 c.clear_ready();assert(c.ready_used()==0&&c.used()==8192);
 char buf[4096];c.consume(h.req,buf);assert(buf[0]==7);
 x={};j={};h={};y={};assert(c.used()==0);
 auto e=c.acquire(a,1,4096);c.publish(e.req,std::make_exception_ptr(std::runtime_error("read failed")));
 assert(c.ready_used()==0);bool failed=false;try{c.consume(e.req,buf);}catch(const std::runtime_error&){failed=true;}assert(failed);e={};
 config().retention="none";auto n=c.acquire(a,1,4096);c.publish(n.req);assert(c.ready_used()==0);n={};assert(c.used()==0);
}
