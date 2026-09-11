#include "qbrain/ai/http_client.hpp"
#include <iostream>
#include <stdexcept>
#include <string>

void test_n46b() {
  using namespace qbrain::ai;
  int checks = 0;
  auto rejected = [&](std::string base, std::string path = "/test", std::string token = "unit-token",
                      int timeout = 100, std::size_t cap = 1024, std::string body = "{}") {
    const auto r = http_post_json(base, path, token, body, timeout, cap);
    if (r.failure != HttpFailure::invalid_request || r.status != 0 || !r.body.empty() || r.error.empty())
      throw std::runtime_error("N46B invalid request was not rejected before transport");
    if (r.error.find("unit-token") != std::string::npos)
      throw std::runtime_error("N46B error leaked input");
    ++checks;
  };
  const std::string base = "http://127.0.0.1:1";
  rejected(""); rejected("ftp://127.0.0.1"); rejected("file:///tmp/file"); rejected("https://");
  rejected("http://user:pass@127.0.0.1"); rejected("http://@127.0.0.1");
  rejected(base+"?key=unit-token"); rejected(base+"#fragment");
  rejected(base+"\r\nX-Injected: yes"); rejected(base+std::string("\0tail",5));
  rejected(base+"\\other"); rejected("http://local host");
  rejected(base,""); rejected(base,"//elsewhere"); rejected(base,"https://elsewhere");
  rejected(base,"/path\nheader"); rejected(base,"/path#fragment"); rejected(base,"/path\\tail");
  rejected(base,"/test","unit-token\r\nX-Injected: yes"); rejected(base,"/test","unit token");
  rejected(base,"/test",std::string("unit-token\0tail",15));
  rejected(base,"/test",std::string(16385,'x'));
  rejected(base,"/test","unit-token",0); rejected(base,"/test","unit-token",-1);
  rejected(base,"/test","unit-token",600001);
  rejected(base,"/test","unit-token",100,0);
  rejected(base,"/test","unit-token",100,HTTP_MAX_RESPONSE_BYTES+1);
  rejected(base,"/test","unit-token",100,1024,std::string(HTTP_MAX_REQUEST_BYTES+1,'x'));
#ifdef _WIN32
  rejected(base+std::string("\xc0\xaf",2));
  rejected(base,std::string("/\xed\xa0\x80",4));
#else
  const auto valid = http_post_json(base,"/test","unit-token","{}",100,1024);
  if (valid.failure != HttpFailure::unsupported_platform || valid.status || !valid.body.empty())
    throw std::runtime_error("N46B non-Windows stub must explicitly report unsupported");
  ++checks;
#endif
  std::cout << "N46B input validation: " << checks << " checks passed\n";
}

#ifdef QBRAIN_HTTP_STANDALONE
int main() {
  try { test_n46b(); return 0; }
  catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
#endif
