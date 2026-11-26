#include "estimator_scalability.h"
#include <cassert>
int main(){using namespace esc;Workload w(100,42,1);std::mt19937_64 a(42),b(42);Estimator x(true,524288),y(false,524288);uint64_t sat=0;
 for(int i=0;i<10000;++i){auto k=w.next(a);assert(k==w.next(b));x.apply(k,true,0,sat);y.apply(k,true,0,sat);}
 for(int i=0;i<100;++i)assert(x.apply(i,false,1,sat)>=y.apply(i,false,1,sat));
 assert(x.bytes()==524288&&x.entries()==0&&sat==0);
 assert((top({1,3,3,2},2)==std::vector<uint64_t>{1,2}));
 std::vector<std::thread> ts;for(int t=0;t<8;++t)ts.emplace_back([&]{uint64_t s=0;for(int i=0;i<1000;++i)y.apply(99,true,0,s);});for(auto& t:ts)t.join();assert(y.apply(99,false,1,sat)>=8000);
}
