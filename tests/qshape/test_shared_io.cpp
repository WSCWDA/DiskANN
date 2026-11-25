#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <thread>
#include <future>
int main(){
 qshape::Coordinator c;auto a=c.acquire({0,4096},1,8192);auto b=c.acquire({0,4096},2,8192);
 assert(a.owner&&!b.owner&&a.req==b.req);
 auto x=c.acquire({4096,4096},2,8192);assert(x.owner);
 assert(!c.acquire({8192,4096},3,8192).req);
 auto y=c.acquire({4096,4096},1,8192);assert(!y.owner);
 std::memset(a.req->data,42,4096);std::memset(x.req->data,43,4096);
 auto f=std::async(std::launch::async,[&]{char buf[4096];c.publish(a.req);c.consume(y.req,buf);assert(buf[0]==43);});
 c.publish(x.req);char buf[4096];c.consume(b.req,buf);assert(buf[0]==42);f.get();
 assert(!c.acquire({0,4096},3,8192).req); // completed payload still pinned
 a={};b={};x={};y={};assert(c.used()==0);
 auto z=c.acquire({0,4096},3,8192);assert(z.owner);
 auto w=c.acquire({0,4096},4,8192);c.publish(z.req,std::make_exception_ptr(std::runtime_error("injected")));
 bool failed=false;try{c.consume(w.req,buf);}catch(const std::runtime_error&){failed=true;}assert(failed);
 z={};w={};assert(c.used()==0&&c.peak()==8192);
 for(int i=0;i<100;++i){auto t=c.acquire({0,4096},1,8192);assert(t.owner);c.publish(t.req);}
}
