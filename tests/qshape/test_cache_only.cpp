#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <thread>
#include <vector>
int main(){
 using namespace qshape;
 config().retention="lru";config().ready_budget=64*4096;
 Coordinator c;Key k{0,4096};const uint64_t b=65536;
 auto a=c.acquire(k,0,b,false), d=c.acquire(k,1,b,false);
 assert(a.owner&&d.owner&&a.req!=d.req);
 std::memset(a.req->data,7,4096);std::memset(d.req->data,7,4096);
 std::thread t([&]{c.publish(a.req);});c.publish(d.req);t.join();
 assert(c.ready_used()==4096);
 auto hit=c.acquire(k,2,b,false);assert(hit.ready_hit&&!hit.owner);
 std::vector<char> dst(4096);c.consume(hit.req,dst.data());assert(dst[0]==7&&dst[4095]==7);
 auto e=c.acquire({4096,4096},3,b,false);assert(e.owner);
 c.publish(e.req,std::make_exception_ptr(std::runtime_error("read failed")));
 auto f=c.acquire({4096,4096},4,b,false);assert(f.owner);c.publish(f.req,std::make_exception_ptr(std::runtime_error("read failed")));
 c.clear_ready();assert(c.ready_used()==0);c.consume(hit.req,dst.data());assert(dst[0]==7);
 a={};d={};hit={};e={};f={};assert(c.used()==0);
 auto x=c.acquire(k,0,b,true),y=c.acquire(k,1,b,true);assert(x.owner&&!y.owner&&x.req==y.req);
 c.publish(x.req);c.clear_ready();
}
