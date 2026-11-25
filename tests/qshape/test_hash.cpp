#include "qshape/shared_io_coordinator.h"
#include <cassert>
#include <set>
#include <thread>
#include <vector>
int main(){
 for(auto policy:{"legacy","mixed"}){
  qshape::config().hash_policy=policy;
  std::set<size_t> ids;
  for(uint64_t i=0;i<65536;++i)ids.insert(qshape::Hash{}({i*4096,4096})%64);
  if(std::string(policy)=="mixed")assert(ids.size()==64);
  qshape::config().shard_stats=true;
  qshape::Coordinator c;
  std::vector<qshape::Query> qs(8);
  std::vector<std::thread> workers;
  for(size_t i=0;i<qs.size();++i)workers.emplace_back([&,i]{
   qshape::Scope scope(&qs[i]);
   for(uint64_t j=0;j<1000;++j){
    auto t=c.acquire({j*4096,4096},i,65536);
    assert(t.req);
    if(t.owner){std::memset(t.req->data,7,4096);c.publish(t.req);}
    char buf[4096];c.consume(t.req,buf);assert(buf[0]==7);
   }
  });
  for(auto& w:workers)w.join();
  uint64_t n=0,o=0,j=0,p=0;
  for(auto& q:qs)for(auto& st:q.shards){n+=st.lookups;o+=st.owners;j+=st.joins;p+=st.publishes;}
  assert(n==8000&&n==o+j&&o==p&&c.used()==0);
 }
}
