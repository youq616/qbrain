#pragma once
// Synthetic fixture commands for the existing HTTP probe, never shipped.
#include "qbrain/ai/embed.hpp"
#include "qbrain/core/brain.hpp"
#include <nlohmann/json.hpp>
#include <stdexcept>

inline nlohmann::json invoke_embedding(const nlohmann::json& j) {
  using J = nlohmann::json;
  qbrain::Config cfg;
  cfg.embedding_base_url = j.at("base");
  cfg.embedding_api_key = j.value("key", "fixture-token");
  cfg.embedding_model = j.value("model", "fixture-embedding");
  cfg.embedding_dimensions = j.value("dimensions", 2);
  if (j["embed"] == "image") {
    const auto bytes = j.value("image_bytes", std::size_t(16));
    if (bytes > 32*1024*1024+1) throw std::runtime_error("fixture input cap");
    const auto r = qbrain::ai::embed_image(cfg, std::string(bytes, 'x'));
    return {{"ok",r.ok},{"unavailable",r.unavailable},{"no_credentials",r.no_credentials},
            {"error",r.error},{"vectors",J::array({r.vector})},{"model",r.model}};
  }
  if (j["embed"] == "job") {
    qbrain::Brain b;
    b.open_at(":memory:"); b.config() = cfg;
    b.db().exec("INSERT INTO pages(id,source_id,slug,title,body,type) VALUES(1,'default','fixture','fixture','fixture','note');"
      "INSERT INTO content_chunks(page_id,chunk_index,text) VALUES(1,0,'first'),(1,1,'second');"
      "INSERT INTO jobs(queue,type,status,payload_json,priority) VALUES('default','embed','waiting','{\"page_id\":1}',50);");
    const auto done = b.drain_embed_jobs(1);
    auto st = b.db().prepare("SELECT status,result_json FROM jobs WHERE type='embed'");
    if (!st.step()) throw std::runtime_error("fixture job missing");
    J vectors = J::array();
    for (const auto& chunk : b.get_chunks(1)) vectors.push_back(chunk.embedding);
    return {{"done",done},{"status",st.column_text(0)},
            {"job_result",J::parse(st.column_text(1))},{"vectors",vectors}};
  }
  auto texts = j.value("texts", std::vector<std::string>{"中文 😀", "second"});
  if (j.value("invalid_utf8",false)) texts = {std::string("\xc0\xaf",2)};
  if (j.contains("repeat_bytes")) {
    const auto bytes = j.at("repeat_bytes").get<std::size_t>();
    if (bytes > 32*1024*1024+1) throw std::runtime_error("fixture input cap");
    texts = {std::string(bytes, static_cast<char>(j.value("repeat_char",1)))};
  }
  const auto r = qbrain::ai::embed_texts(cfg,texts);
  return {{"ok",r.ok},{"error",r.error},{"vectors",r.vectors},{"model",r.model}};
}
