#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <thread>
#include <vector>
#include <array>
#include <stdexcept>
int main(){
 using namespace qshape;
 config()=Config{};config().retention="frequency";config().frequency_mode="cms";config().frequency_budget=524288;
 Coordinator c;Key k{4096,4096};auto owner=c.acquire(k,0,67108864);assert(owner.owner);
 std::memset(owner.req->data,42,4096);
 std::atomic<unsigned> joined{0};std::vector<std::thread> ts;
 for(unsigned i=0;i<16;++i)ts.emplace_back([&,i]{Query q;Scope scope(&q);auto t=c.acquire(k,i+1,67108864);assert(t.req&&!t.owner&&!t.ready_hit);++joined;std::array<unsigned char,4096> dst;c.consume(t.req,dst.data());for(auto v:dst)assert(v==42);assert(q.frequency_updates==1);});
 while(joined.load()!=16)std::this_thread::yield();
 c.publish(owner.req);for(auto& t:ts)t.join();
 assert(c.acquire(k,99,67108864,false).ready_hit);
 c.clear_ready();assert(c.ready_used()==0);owner.req.reset();assert(c.used()==0);
 auto a=c.acquire(k,1,67108864,false),b=c.acquire(k,2,67108864,false);assert(a.owner&&b.owner&&a.req!=b.req);
 c.publish(a.req);c.publish(b.req);assert(c.ready_used()==4096);
 c.clear_ready();a.req.reset();b.req.reset();assert(c.used()==0);
 auto e=c.acquire(k,1,67108864);auto j=c.acquire(k,2,67108864);assert(!j.owner);
 std::atomic<bool> caught{false};std::thread waiter([&]{std::array<char,4096> dst;try{c.consume(j.req,dst.data());}catch(const std::runtime_error&){caught=true;}});
 c.publish(e.req,std::make_exception_ptr(std::runtime_error("injected")));waiter.join();assert(caught);
 e.req.reset();j.req.reset();assert(c.used()==0);
}
