#include "qshape/shared_io_coordinator.h"
#include <cassert>
int main(){
 qshape::ShadowStats s;
 s.decision(true,true,5,4);s.decision(false,false,4,4);s.decision(true,false,3,4);s.decision(false,true,5,4);
 assert(s.checks==4&&s.aa==1&&s.rr==1&&s.fa==1&&s.fr==1);
 s.error(5,3,true);s.error(2,3,false);assert(s.under==1&&s.candidate_error[1]==1);
 auto& c=qshape::config();c.retention="frequency";c.frequency_mode="cms";c.frequency_shadow=true;c.ready_budget=64*4096;
 qshape::Coordinator co;
 auto a=co.acquire({0,4096},0,65536);assert(a.owner);
 auto b=co.acquire({0,4096},1,65536);assert(!b.owner);
 co.publish(a.req);auto d=co.acquire({0,4096},2,65536);assert(d.ready_hit);
 co.clear_ready();
}
