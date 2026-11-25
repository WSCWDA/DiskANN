#include "qshape/shared_io_coordinator.h"
#include <cassert>
int main(){
 using namespace qshape;
 config().region_trace=true;config().retention="bounded-local";config().ready_budget=64*4096;
 Query q;q.id=7;Scope scope(&q);Coordinator c;
 auto a=c.acquire({4096,4096},7,65536);assert(a.owner);
 auto b=c.acquire({4096,4096},7,65536);assert(!b.owner);
 c.publish(a.req);
 auto d=c.acquire({4096,4096},7,65536);assert(d.ready_hit);
 assert(q.regions.size()==5);
 const char* kinds[]={"OWNER","INFLIGHT_JOIN","PUBLISH","ADMIT","READY_HIT"};
 for(size_t i=0;i<5;++i){assert(std::string(q.regions[i].kind)==kinds[i]);assert(q.regions[i].life==1);}
 config().region_event_limit=5;c.acquire({4096,4096},7,65536);assert(q.region_dropped==1);
 c.clear_ready();
}
