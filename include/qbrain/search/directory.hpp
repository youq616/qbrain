#pragma once
#include "qbrain/core/brain.hpp"
#include "qbrain/core/types.hpp"
#include <string>
#include <vector>

namespace qbrain::search {

struct DirectoryScope {
  std::string source_id;
  std::string space;
  std::string slug_prefix;
  std::string uri;
};

struct DirectorySearchOpts {
  int limit = 10;
  int rrf_k = 60;
  std::string mode = "balanced";
  bool rerank = false;
  bool rerank_llm = false;
  const Config* config = nullptr;
};

DirectoryScope parse_directory_scope(Brain& brain, const std::string& uri);

std::vector<SearchHit> directory_search(Brain& brain, const std::string& query,
                                        const std::vector<float>* query_embedding,
                                        const DirectoryScope& scope,
                                        const DirectorySearchOpts& opts);

}  // namespace qbrain::search
