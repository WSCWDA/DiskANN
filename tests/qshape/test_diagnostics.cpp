#include "qshape/shared_io_coordinator.h"
#include <cassert>
int main(){
 qshape::config().breakdown=true;qshape::config().reuse_stats=true;
 qshape::Coordinator c;qshape::Query a,b;b.id=1;
 {qshape::Scope scope(&a);auto t=c.acquire({0,4096},0,8192);assert(t.owner);
 auto j=c.acquire({0,4096},0,8192);assert(!j.owner);
 std::memset(t.req->data,42,4096);c.publish(t.req);char buf[4096];
 c.consume(t.req,buf,true);c.consume(j.req,buf,false);assert(buf[0]==42);}
 {qshape::Scope scope(&b);auto t=c.acquire({0,4096},1,8192);assert(t.owner);
 assert(b.reuse_hits==1&&b.reuse_cross_query==1&&b.reuse_same_group==1&&b.reuse.size()==1);
 c.publish(t.req);}
 assert(a.owner_consumes==1&&a.consumer_consumes==1&&a.ready_before_wait_count==1&&a.copy_bytes==8192);
 assert(c.used()==0);
}
