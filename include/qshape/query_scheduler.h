#pragma once
#include "baseline.h"
#include <algorithm>
#include <mutex>
#include <limits>
namespace qshape {
struct SchedulerConfig { std::string policy="reorder"; uint32_t lookahead=4; };
inline SchedulerConfig& scheduler_config(){static SchedulerConfig c;return c;}
class GroupScheduler {
 struct Group {size_t next,end,active=0;};
 std::vector<Group> groups;
 std::mutex mu;
 size_t first=0,window;
public:
 explicit GroupScheduler(size_t n,size_t size,size_t w):window(w){
  if(!size||!w)throw std::invalid_argument("invalid scheduler configuration");
  for(size_t i=0;i<n;){size_t end=i+std::min(size,n-i);groups.push_back({i,end,0});i=end;}
 }
 static size_t none(){return std::numeric_limits<size_t>::max();}
 size_t take(){
  std::lock_guard<std::mutex> lock(mu);
  while(first<groups.size()&&groups[first].next==groups[first].end)++first;
  if(first==groups.size())return none();
  size_t best=first;
  // Prefer the most populated active group within a bounded pending-group window.
  for(size_t j=first;j<groups.size()&&j-first<window;++j)
   if(groups[j].next<groups[j].end&&groups[j].active>groups[best].active)best=j;
  auto& g=groups[best];++g.active;return g.next++;
 }
 void done(size_t group){
  std::lock_guard<std::mutex> lock(mu);
  if(group>=groups.size()||!groups[group].active)throw std::logic_error("invalid completion");
  --groups[group].active;
 }
};
}
