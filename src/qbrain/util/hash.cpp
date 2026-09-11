#include "qbrain/util/hash.hpp"
#include <array>
#include <bit>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace qbrain::util {
namespace {
// SHA-256, FIPS 180-4 sections 4.2.2 and 6.2; no platform-specific fallback.
constexpr uint32_t k[64] = {
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
void compress(std::array<uint32_t,8>& h, const unsigned char* p) {
  uint32_t w[64];
  for (int i=0;i<16;++i) w[i]=(uint32_t(p[i*4])<<24)|(uint32_t(p[i*4+1])<<16)|
                               (uint32_t(p[i*4+2])<<8)|uint32_t(p[i*4+3]);
  for (int i=16;i<64;++i) {
    const auto a=w[i-15], b=w[i-2];
    w[i]=w[i-16]+(std::rotr(a,7)^std::rotr(a,18)^(a>>3))+w[i-7]+
          (std::rotr(b,17)^std::rotr(b,19)^(b>>10));
  }
  auto a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],z=h[7];
  for (int i=0;i<64;++i) {
    const auto t1=z+(std::rotr(e,6)^std::rotr(e,11)^std::rotr(e,25))+((e&f)^((~e)&g))+k[i]+w[i];
    const auto t2=(std::rotr(a,2)^std::rotr(a,13)^std::rotr(a,22))+((a&b)^(a&c)^(b&c));
    z=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
  }
  h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=z;
}
}
std::string sha256_hex(std::string_view data) {
  if (data.size()>std::numeric_limits<uint64_t>::max()/8) throw std::length_error("SHA-256 input too large");
  std::array<uint32_t,8> h={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
  auto p=reinterpret_cast<const unsigned char*>(data.data());
  std::size_t i=0;
  for (;data.size()-i>=64;i+=64) compress(h,p+i);
  std::array<unsigned char,128> tail{};
  const auto remain=data.size()-i;
  if (remain) std::memcpy(tail.data(),p+i,remain);
  tail[remain]=0x80;
  const std::size_t n=remain<56?64:128;
  const uint64_t bits=static_cast<uint64_t>(data.size())*8;
  for (int j=0;j<8;++j) tail[n-1-j]=static_cast<unsigned char>(bits>>(8*j));
  compress(h,tail.data()); if(n==128) compress(h,tail.data()+64);
  constexpr char hex[]="0123456789abcdef";
  std::string result; result.reserve(64);
  for (auto v:h) for(int j=7;j>=0;--j) result.push_back(hex[(v>>(j*4))&15]);
  return result;
}
std::string content_hash(std::string_view title, std::string_view body) {
  std::string s; s.reserve(title.size()+body.size()+1); s.append(title); s.push_back('\n'); s.append(body);
  return sha256_hex(s);
}
}
