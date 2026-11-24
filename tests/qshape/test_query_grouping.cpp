#include "qshape/query_grouping.h"
#include <cassert>
int main(){
 float x[]={0,0,100,100,1,1,101,101,2,2};
 qshape::GroupingConfig c;c.group_size=2;c.candidate_pool=4;
 auto a=qshape::group_queries(x,5,2,2,c,"l2");assert(a.order[0]==0&&a.order[4]==4);
 c.policy="similarity";a=qshape::group_queries(x,5,2,2,c,"l2");assert(a.order[0]==0&&a.order[1]==2);
 auto sorted=a.order;std::sort(sorted.begin(),sorted.end());for(unsigned i=0;i<5;++i)assert(sorted[i]==i);
 c.policy="random";auto b=qshape::group_queries(x,5,2,2,c,"l2");auto d=qshape::group_queries(x,5,2,2,c,"l2");assert(b.order==d.order);
 c.policy="similarity";c.group_size=1;a=qshape::group_queries(x,5,2,2,c,"cosine");assert(a.order.size()==5);
}
