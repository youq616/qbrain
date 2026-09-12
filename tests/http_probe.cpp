// Loopback fixture driver; not included in the installed Qbrain application.
#include "qbrain/ai/http_client.hpp"
#include "qbrain/ai/chat.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/core/brain.hpp"
#include <nlohmann/json.hpp>
#include <chrono>
#include <future>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

using J = nlohmann::json;
J invoke(const J& j) {
  const auto start = std::chrono::steady_clock::now();
  J result;
  if (j.value("embedding",false)) {
    qbrain::Config cfg;
    cfg.embedding_base_url=j.at("base"); cfg.embedding_model="fixture-model";
    cfg.embedding_dimensions=j.value("dimensions",3); cfg.embedding_api_key="fixture-token";
    if (j.value("image",false)) {
      const auto r=qbrain::ai::embed_image(cfg,"synthetic-image-bytes");
      result={{"ok",r.ok},{"unavailable",r.unavailable},{"vectors",J::array({r.vector})},{"error",r.error},{"model",r.model}};
    } else {
      const auto texts=j.value("texts",std::vector<std::string>{"one","two"});
      const auto r=qbrain::ai::embed_texts(cfg,texts);
      result={{"ok",r.ok},{"vectors",r.vectors},{"error",r.error},{"model",r.model}};
    }
  } else if (j.value("chat",false)) {
    qbrain::Config cfg;
    cfg.chat_base_url=j.at("base"); cfg.chat_model="loopback-fixture";
    cfg.chat_endpoint="chat/completions"; cfg.chat_api_key="fixture-token";
    const auto r=qbrain::ai::chat_complete(cfg,{{"user","fixture"}},0.0,j.value("timeout",2000));
    result={{"ok",r.ok},{"body",r.content},{"error",r.error},{"chat_failure",static_cast<int>(r.failure_kind)}};
  } else {
    const auto r=qbrain::ai::http_post_json(j.at("base").get<std::string>(),j.value("path","/ok"),
        j.value("token","fixture-token"),j.value("body","{}"),j.value("timeout",2000),
        j.value("cap",std::size_t(1024)));
    result={{"status",r.status},{"body",r.body},{"error",r.error},{"failure",static_cast<int>(r.failure)}};
  }
  result["elapsed_ms"]=std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::steady_clock::now()-start).count();
  return result;
}
int main() {
  try {
    std::string line;
    while (std::getline(std::cin,line)) {
      if (line.size()>1024*1024) throw std::runtime_error("fixture command too large");
      const J j=J::parse(line); J out;
      if (j.contains("batch")) {
        if (!j["batch"].is_array() || j["batch"].size()>128) throw std::runtime_error("fixture batch too large");
        out["results"]=J::array();
        if (j.value("parallel",false)) {
          if (j["batch"].size()>16) throw std::runtime_error("fixture concurrency too large");
          std::vector<std::future<J>> calls;
          for (const auto& item:j["batch"]) calls.push_back(std::async(std::launch::async,[item]{return invoke(item);}));
          for (auto& call:calls) out["results"].push_back(call.get());
        } else {
          for (const auto& item:j["batch"]) out["results"].push_back(invoke(item));
        }
        const int settle_ms=j.value("handle_settle_ms",250);
        if (settle_ms<250 || settle_ms>2000) throw std::runtime_error("invalid handle sample delay");
        std::this_thread::sleep_for(std::chrono::milliseconds(250));
#ifdef _WIN32
        DWORD count=0;
        if (!GetProcessHandleCount(GetCurrentProcess(),&count)) throw std::runtime_error("handle diagnostics failed");
        out["process_handles_at_250ms"]=count;
        // Network calls have already returned; this fixed, bounded observation
        // delay is not added to any request deadline. A leaked handle will not
        // disappear just because the peer/WinHTTP teardown has settled.
        std::this_thread::sleep_for(std::chrono::milliseconds(settle_ms-250));
        if (!GetProcessHandleCount(GetCurrentProcess(),&count)) throw std::runtime_error("handle diagnostics failed");
        out["process_handles"]=count;
        out["handle_settle_ms"]=settle_ms;
#endif
      } else out=invoke(j);
      std::cout<<out.dump()<<std::endl;
    }
    return 0;
  } catch (const std::exception&) {
    std::cerr<<"HTTP fixture driver failed\n"; return 1;
  }
}
