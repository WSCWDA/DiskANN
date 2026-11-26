#pragma once
#include <array>
#include <cstdint>
namespace qshape {
struct ShadowStats {
 uint64_t updates=0,failures=0,invalid=0,entries=0,checks=0,aa=0,rr=0,fa=0,fr=0,victims=0,under=0;
 std::array<uint64_t,7> candidate_error{},victim_error{};
 std::array<std::array<uint64_t,7>,4> margin{};
 static unsigned bucket(uint64_t n){return n==0?0:n<=4?1:n<=16?2:n<=64?3:n<=256?4:n<=1024?5:6;}
 void error(uint64_t est,uint64_t exact,bool candidate){if(est<exact)++under; (candidate?candidate_error:victim_error)[bucket(est>=exact?est-exact:exact-est)]++;}
 void decision(bool cms,bool exact,uint64_t c,uint64_t v){
  ++checks;unsigned k=cms?(exact?0:2):(exact?3:1);
  if(k==0)++aa;else if(k==1)++rr;else if(k==2)++fa;else ++fr;
  ++margin[k][bucket(c>=v?c-v:v-c)];
 }
};
}
