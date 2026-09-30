#include "qbrain/search/directory.hpp"
#include "qbrain/ai/embedding_policy.hpp"
#include "qbrain/search/detail/exact_topk.hpp"
#include "qbrain/search/result_identity.hpp"
#include "qbrain/search/rerank.hpp"
#include "qbrain/search/rrf.hpp"
#include "qbrain/search/vector.hpp"
#include "qbrain/util/string_util.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace qbrain::search {
namespace {

std::string namespace_filter(const std::string& space) {
  if (space == "memories") return "p.type='session_fragment'";
  if (space == "skills") return "p.type='skill'";
  return "p.type NOT IN ('session_fragment','skill')";
}

bool has_prefix(const std::string& slug, const std::string& prefix) {
  return prefix.empty() ||
         (slug.size() >= prefix.size() &&
          std::equal(prefix.begin(), prefix.end(), slug.begin()));
}

std::vector<std::string> query_terms(const std::string& query) {
  std::vector<std::string> out;
  for (auto part : util::split(util::to_lower(query), ' ')) {
    part = util::trim(part);
    if (part.empty()) continue;
    if (part.size() > 256) part.resize(256);
    out.push_back(std::move(part));
    if (out.size() == 16) break;
  }
  if (out.empty()) out.push_back(util::to_lower(util::trim(query)));
  return out;
}

double lexical_score(const std::string& query_lower,
                     const std::vector<std::string>& terms,
                     const std::string& slug,
                     const std::string& title,
                     const std::string& body) {
  const auto s = util::to_lower(slug);
  const auto t = util::to_lower(title);
  const auto b = util::to_lower(body);
  double score = 0.0;
  if (!query_lower.empty()) {
    if (t.find(query_lower) != std::string::npos) score += 100.0;
    if (s.find(query_lower) != std::string::npos) score += 80.0;
    if (b.find(query_lower) != std::string::npos) score += 40.0;
  }
  for (const auto& term : terms) {
    if (term.empty()) continue;
    if (t.find(term) != std::string::npos) score += 10.0;
    if (s.find(term) != std::string::npos) score += 8.0;
    if (b.find(term) != std::string::npos) score += 4.0;
  }
  return score;
}

void retain_lexical(std::vector<SearchHit>& hits, SearchHit hit, int candidate_limit) {
  hits.push_back(std::move(hit));
  if (hits.size() <= static_cast<std::size_t>(candidate_limit * 2)) return;
  std::sort(hits.begin(), hits.end(), [](const SearchHit& a, const SearchHit& b) {
    return a.score != b.score ? a.score > b.score : result_identity_less(a, b);
  });
  hits.resize(static_cast<std::size_t>(candidate_limit));
}

std::vector<SearchHit> lexical_directory_search(Brain& brain, const std::string& query,
                                                const DirectoryScope& scope,
                                                int candidate_limit) {
  std::vector<SearchHit> out;
  const auto query_lower = util::to_lower(util::trim(query));
  const auto terms = query_terms(query);
  auto statement = brain.db().prepare(
      "SELECT p.id,p.slug,p.title,p.type,p.body FROM pages p "
      "WHERE p.source_id=? AND p.deleted_at IS NULL AND " +
      namespace_filter(scope.space) + " ORDER BY p.slug,p.id");
  statement.bind_text(1, scope.source_id);
  while (statement.step()) {
    const auto slug = statement.column_text(1);
    if (!has_prefix(slug, scope.slug_prefix)) continue;
    const auto title = statement.column_text(2);
    const auto body = statement.column_text(4);
    const double score = lexical_score(query_lower, terms, slug, title, body);
    if (score <= 0.0) continue;
    SearchHit hit;
    hit.page_id = statement.column_int(0);
    hit.source_id = scope.source_id;
    hit.slug = slug;
    hit.title = title;
    hit.type = statement.column_text(3);
    hit.snippet = util::utf8_excerpt(body, 200, true);
    hit.score = score;
    retain_lexical(out, std::move(hit), candidate_limit);
  }
  std::sort(out.begin(), out.end(), [](const SearchHit& a, const SearchHit& b) {
    return a.score != b.score ? a.score > b.score : result_identity_less(a, b);
  });
  if (out.size() > static_cast<std::size_t>(candidate_limit))
    out.resize(static_cast<std::size_t>(candidate_limit));
  for (std::size_t i = 0; i < out.size(); ++i)
    out[i].fts_rank = static_cast<double>(i + 1);
  return out;
}

std::vector<SearchHit> vector_directory_search(Brain& brain,
                                               const std::vector<float>& qemb,
                                               const DirectoryScope& scope,
                                               int candidate_limit,
                                               const std::string& model) {
  if (qemb.empty() ||
      !std::all_of(qemb.begin(), qemb.end(),
                   [](float value) { return std::isfinite(value); }))
    return {};
  if (!model.empty() &&
      std::none_of(qemb.begin(), qemb.end(),
                   [](float value) { return value != 0.0f; }))
    return {};

  detail::ExactPageTopK best(candidate_limit);
  auto statement = brain.db().prepare(
      "SELECT c.page_id,p.slug,p.title,p.type,c.text,c.embedding,p.source_id "
      "FROM content_chunks c JOIN pages p ON p.id=c.page_id "
      "WHERE p.source_id=? AND p.deleted_at IS NULL AND c.embedding IS NOT NULL AND " +
      namespace_filter(scope.space) +
      (model.empty() ? "" : " AND c.model=? AND c.dim=?") +
      " ORDER BY p.slug,p.id,c.chunk_index");
  int bind = 1;
  statement.bind_text(bind++, scope.source_id);
  if (!model.empty()) {
    statement.bind_text(bind++, model);
    statement.bind_int(bind++, static_cast<int64_t>(qemb.size()));
  }
  while (statement.step()) {
    const auto slug = statement.column_text(1);
    if (!has_prefix(slug, scope.slug_prefix)) continue;
    const auto emb = unpack_f32(statement.column_blob(5));
    if (emb.size() != qemb.size() ||
        !std::all_of(emb.begin(), emb.end(),
                     [](float value) { return std::isfinite(value); }))
      continue;
    if (!model.empty() &&
        std::none_of(emb.begin(), emb.end(),
                     [](float value) { return value != 0.0f; }))
      continue;
    const double similarity = cosine_similarity(qemb, emb);
    if (!std::isfinite(similarity) || best.below_threshold(similarity)) continue;
    SearchHit hit;
    hit.page_id = statement.column_int(0);
    hit.source_id = statement.column_text(6);
    hit.slug = slug;
    hit.title = statement.column_text(2);
    hit.type = statement.column_text(3);
    hit.snippet = util::utf8_excerpt(statement.column_text(4), 200, true);
    hit.score = similarity;
    best.consider(std::move(hit));
  }
  auto out = best.results();
  for (std::size_t i = 0; i < out.size(); ++i)
    out[i].vector_rank = static_cast<double>(i + 1);
  return out;
}

}  // namespace

DirectoryScope parse_directory_scope(Brain& brain, const std::string& uri) {
  if (uri.empty() || uri.size() > 2048 || !util::valid_utf8(uri) ||
      uri.back() != '/')
    throw std::invalid_argument("directory_uri_required");
  for (const unsigned char c : uri)
    if (c < 32 || c == 127 || c == '%' || c == '\\' || c == '?' || c == '#')
      throw std::invalid_argument("invalid_directory_uri");
  constexpr std::string_view scheme = "qbrain://";
  if (uri.rfind(scheme, 0) != 0)
    throw std::invalid_argument("invalid_directory_uri");
  const auto source_end = uri.find('/', scheme.size());
  if (source_end == std::string::npos)
    throw std::invalid_argument("invalid_directory_uri");
  const auto source = uri.substr(scheme.size(), source_end - scheme.size());
  const auto canonical = Brain::canonical_source_id(source);
  if (!canonical || *canonical != source || !brain.source_exists(source))
    throw std::invalid_argument("invalid_directory_source");
  const auto space_end = uri.find('/', source_end + 1);
  if (space_end == std::string::npos)
    throw std::invalid_argument("invalid_directory_uri");
  const auto space = uri.substr(source_end + 1, space_end - source_end - 1);
  if (space != "resources" && space != "skills" && space != "memories")
    throw std::invalid_argument("invalid_directory_namespace");
  auto prefix = uri.substr(space_end + 1);
  if (!prefix.empty() && prefix.back() == '/') prefix.pop_back();
  if (!prefix.empty()) {
    std::size_t start = 0;
    while (start < prefix.size()) {
      const auto end = prefix.find('/', start);
      const auto stop = end == std::string::npos ? prefix.size() : end;
      const auto component = prefix.substr(start, stop - start);
      if (component.empty() || component == "." || component == "..")
        throw std::invalid_argument("invalid_directory_uri");
      start = stop + 1;
    }
    prefix.push_back('/');
  }
  return {source, space, prefix, uri};
}

std::vector<SearchHit> directory_search(Brain& brain, const std::string& query,
                                        const std::vector<float>* query_embedding,
                                        const DirectoryScope& scope,
                                        const DirectorySearchOpts& opts) {
  if (util::trim(query).empty())
    throw std::invalid_argument("search_query_required");
  const int limit = std::clamp(opts.limit, 1, 100);
  int candidates = limit * 3;
  bool use_vector = query_embedding && !query_embedding->empty();
  if (opts.mode == "conservative") {
    candidates = limit * 2;
    use_vector = false;
  } else if (opts.mode == "tokenmax") {
    candidates = limit * 5;
  } else if (opts.mode != "balanced" && !opts.mode.empty()) {
    throw std::invalid_argument("invalid_search_mode");
  }
  candidates = std::clamp(candidates, 1, 500);

  std::vector<std::vector<SearchHit>> lists;
  lists.push_back(lexical_directory_search(brain, query, scope, candidates));
  const Config& config = opts.config ? *opts.config : brain.config();
  const auto model = ai::active_embedding_model(config);
  if (use_vector && ai::valid_embedding_model(model))
    lists.push_back(vector_directory_search(brain, *query_embedding, scope,
                                            candidates, model));

  auto fused = rrf_fusion(lists, opts.rrf_k);
  std::sort(fused.begin(), fused.end(), [](const SearchHit& a, const SearchHit& b) {
    return a.score != b.score ? a.score > b.score : result_identity_less(a, b);
  });

  const bool do_rerank = opts.rerank || opts.mode == "tokenmax";
  if (do_rerank && !fused.empty()) {
    RerankerOpts rerank;
    rerank.enabled = true;
    rerank.top_n_in = std::min(30, static_cast<int>(fused.size()));
    rerank.use_llm = opts.rerank_llm || opts.mode == "tokenmax";
    if (rerank.use_llm && resolve_api_key(config, true).empty())
      rerank.use_llm = false;
    fused = apply_reranker(config, query, std::move(fused), rerank);
  }

  if (fused.size() >= 3) {
    const double top = fused[0].score;
    std::size_t cut = fused.size();
    for (std::size_t i = 1; i < fused.size(); ++i) {
      if (top > 0.0 && ((top - fused[i].score) / top) >= 0.35) {
        cut = i;
        break;
      }
    }
    if (cut < fused.size() && cut >= 1) fused.resize(cut);
  }
  if (fused.size() > static_cast<std::size_t>(limit))
    fused.resize(static_cast<std::size_t>(limit));
  return fused;
}

}  // namespace qbrain::search
