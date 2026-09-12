#pragma once
// Frozen MIT Qbrain hybrid.cpp at c9f3ed5; only namespace/free-function names changed.
// Test oracle only. Never linked into the production application.
#include "qbrain/search/hybrid.hpp"
#include "qbrain/search/result_identity.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <cmath>
#include <utility>
#include "qbrain/search/rerank.hpp"
#include "qbrain/search/rrf.hpp"
#include "qbrain/search/vector.hpp"
#include "qbrain/util/string_util.hpp"
#include <algorithm>
#include <unordered_map>

namespace qbrain::search::n46c_reference {

namespace {
// FtsRow predates source identity. Resolve all candidates in one read instead
// of adding one SQL query per hit or changing both storage backend contracts.
// Deleted/stale rows and unknown sources are never silently mapped to default.
void attach_sources(Brain& brain, std::vector<SearchHit>& hits,
                    const std::string& requested_source) {
  if (hits.empty()) return;
  std::string sql = "SELECT id, source_id, slug FROM pages WHERE deleted_at IS NULL AND id IN (";
  for (size_t i = 0; i < hits.size(); ++i) sql += i ? ",?" : "?";
  sql += ")";
  auto st = brain.db().prepare(sql);
  for (size_t i = 0; i < hits.size(); ++i) st.bind_int(static_cast<int>(i + 1), hits[i].page_id);
  std::unordered_map<int64_t, std::pair<std::string, std::string>> identities;
  while (st.step()) identities.emplace(st.column_int(0), std::make_pair(st.column_text(1), st.column_text(2)));
  hits.erase(std::remove_if(hits.begin(), hits.end(), [&](SearchHit& h) {
    const auto it = identities.find(h.page_id);
    if (it == identities.end() || it->second.first.empty() || it->second.second != h.slug ||
        (!requested_source.empty() && it->second.first != requested_source)) return true;
    h.source_id = it->second.first;
    h.snippet = util::utf8_excerpt(h.snippet, h.snippet.size());
    return false;
  }), hits.end());
}
}  // namespace

std::vector<SearchHit> reference_fts_search(Brain& brain, const std::string& query, int limit,
                                  const std::string& source_id) {
  std::vector<SearchHit> out;
  limit = std::clamp(limit, 1, 500);
  // N38 D0.5 (P0-3): the FTS5 MATCH statement now lives behind the storage
  // backend seam (IStorageBackend::fts_search / SqliteBackend::fts_search --
  // same SQL text, same bind order, same backend-side query quoting moved
  // verbatim). Rank-counter/score conversion stays here; the LIKE fallback
  // path below is unchanged.
  try {
    auto rows = brain.db().fts_search(query, limit, source_id);
    int rank = 1;
    for (auto& r : rows) {
      SearchHit h;
      h.page_id = r.page_id;
      h.slug = std::move(r.slug);
      h.title = std::move(r.title);
      h.type = std::move(r.type);
      h.snippet = std::move(r.snippet);
      h.fts_rank = static_cast<double>(rank);
      h.score = -r.rank;
      out.push_back(std::move(h));
      ++rank;
    }
  } catch (...) {
    out.clear();  // do not mix partial FTS output with the fallback
    std::string sql2 =
        "SELECT id, slug, title, type, substr(body,1,160) FROM pages "
        "WHERE deleted_at IS NULL AND (title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' "
        "OR slug LIKE ? ESCAPE '\\')";
    if (!source_id.empty()) sql2 += " AND source_id = ?";
    // n38: expression-level COLLATE removed for cross-backend SQL; the slug
    // column carries BINARY collation at DDL level (SQLite) / "C" (PG schema),
    // which is byte-identical to the previous expression form on SQLite.
    sql2 += " ORDER BY updated_at DESC, slug ASC LIMIT ?";
    auto st2 = brain.db().prepare(sql2);
    // Escape LIKE wildcards so user input is literal.
    std::string esc = query;
    esc = util::replace_all(esc, "\\", "\\\\");
    esc = util::replace_all(esc, "%", "\\%");
    esc = util::replace_all(esc, "_", "\\_");
    std::string like = "%" + esc + "%";
    int idx = 1;
    st2.bind_text(idx++, like);
    st2.bind_text(idx++, like);
    st2.bind_text(idx++, like);
    if (!source_id.empty()) st2.bind_text(idx++, source_id);
    st2.bind_int(idx, limit);
    int rank = 1;
    while (st2.step()) {
      SearchHit h;
      h.page_id = st2.column_int(0);
      h.slug = st2.column_text(1);
      h.title = st2.column_text(2);
      h.type = st2.column_text(3);
      h.snippet = st2.column_text(4);
      h.fts_rank = static_cast<double>(rank++);
      out.push_back(std::move(h));
    }
  }
  attach_sources(brain, out, source_id);
  return out;
}

std::vector<SearchHit> reference_vector_search(Brain& brain, const std::vector<float>& qemb, int limit,
                                     const std::string& source_id) {
  std::vector<SearchHit> out;
  if (qemb.empty() || !std::all_of(qemb.begin(), qemb.end(), [](float v) { return std::isfinite(v); })) return out;
  limit = std::clamp(limit, 1, 500);
  std::string sql =
      "SELECT c.page_id, p.slug, p.title, p.type, c.text, c.embedding, p.source_id "
      "FROM content_chunks c JOIN pages p ON p.id = c.page_id "
      "WHERE p.deleted_at IS NULL AND c.embedding IS NOT NULL";
  if (!source_id.empty()) sql += " AND p.source_id = ?";
  auto st = brain.db().prepare(sql);
  if (!source_id.empty()) st.bind_text(1, source_id);
  struct Cand {
    SearchHit h;
    double sim;
  };
  std::vector<Cand> cands;
  while (st.step()) {
    auto blob = st.column_blob(5);
    auto emb = unpack_f32(blob);
    if (emb.size() != qemb.size() || !std::all_of(emb.begin(), emb.end(), [](float v) { return std::isfinite(v); })) continue;
    double sim = cosine_similarity(qemb, emb);
    if (!std::isfinite(sim)) continue;
    SearchHit h;
    h.page_id = st.column_int(0);
    h.slug = st.column_text(1);
    h.title = st.column_text(2);
    h.type = st.column_text(3);
    h.snippet = util::utf8_excerpt(st.column_text(4), 200);
    h.source_id = st.column_text(6);
    h.score = sim;
    cands.push_back({std::move(h), sim});
  }
  std::unordered_map<std::string, Cand> best;
  for (auto& c : cands) {
    const auto key = result_identity(c.h);
    auto it = best.find(key);
    if (it == best.end() || c.sim > it->second.sim ||
        (c.sim == it->second.sim && c.h.snippet < it->second.h.snippet))
      best[key] = std::move(c);
  }
  std::vector<Cand> uniq;
  uniq.reserve(best.size());
  for (auto& [_, c] : best) uniq.push_back(std::move(c));
  std::sort(uniq.begin(), uniq.end(),
            [](const Cand& a, const Cand& b) {
              return a.sim != b.sim ? a.sim > b.sim : result_identity_less(a.h, b.h);
            });
  if (static_cast<int>(uniq.size()) > limit) uniq.resize(static_cast<size_t>(limit));
  int rank = 1;
  for (auto& c : uniq) {
    c.h.vector_rank = static_cast<double>(rank++);
    c.h.score = c.sim;
    out.push_back(std::move(c.h));
  }
  return out;
}

std::vector<SearchHit> reference_hybrid_search(Brain& brain, const std::string& query,
                                     const std::vector<float>* qemb, const HybridOpts& opts) {
  int limit = std::clamp(opts.limit, 1, 100);
  int cand = limit * 3;
  bool use_vec = opts.use_vector;
  if (opts.mode == "conservative") {
    use_vec = false;
    cand = limit * 2;
  } else if (opts.mode == "tokenmax") {
    cand = limit * 5;
  }
  if (opts.candidate_budget_out) *opts.candidate_budget_out = cand;
  auto fts = reference_fts_search(brain, query, cand, opts.source_id);
  std::vector<std::vector<SearchHit>> lists;
  lists.push_back(fts);
  if (use_vec && qemb && !qemb->empty()) {
    lists.push_back(reference_vector_search(brain, *qemb, cand, opts.source_id));
  }
  auto fused = rrf_fusion(lists, opts.rrf_k);
  // N3 post-fusion: title / backlink boosts (lightweight)
  for (auto& h : fused) {
    auto ql = util::to_lower(query);
    auto tl = util::to_lower(h.title);
    if (!tl.empty() && tl.find(ql) != std::string::npos) h.score *= 1.25;
    else if (!ql.empty() && !tl.empty()) {
      // token overlap
      for (auto& tok : util::split(ql, ' ')) {
        if (tok.size() > 2 && tl.find(tok) != std::string::npos) {
          h.score *= 1.08;
          break;
        }
      }
    }
    auto backs = brain.get_links_to(h.slug, h.source_id);
    if (!backs.empty()) h.score *= (1.0 + 0.05 * std::min<size_t>(backs.size(), 5));
  }
  std::sort(fused.begin(), fused.end(), [](const SearchHit& a, const SearchHit& b) {
    return a.score != b.score ? a.score > b.score : result_identity_less(a, b);
  });

  // N12: fail-open rerank (local always; optional LLM). tokenmax enables by default.
  bool do_rerank = opts.rerank || opts.mode == "tokenmax";
  if (do_rerank) {
    RerankerOpts ro;
    ro.enabled = true;
    ro.top_n_in = std::min(30, static_cast<int>(fused.size()));
    ro.use_llm = opts.rerank_llm || opts.mode == "tokenmax";
    Config empty_cfg;
    const Config& cfg = opts.config ? *opts.config : empty_cfg;
    if (ro.use_llm && resolve_api_key(cfg, true).empty()) ro.use_llm = false;
    fused = apply_reranker(cfg, query, std::move(fused), ro);
  }

  // autocut: drop long tail if score gap large
  if (opts.pre_autocut_count_out) *opts.pre_autocut_count_out = static_cast<int>(fused.size());
  if (fused.size() >= 3) {
    double top = fused[0].score;
    size_t cut = fused.size();
    for (size_t i = 1; i < fused.size(); ++i) {
      if (top > 0 && ((top - fused[i].score) / top) >= 0.35) {
        cut = i;
        break;
      }
    }
    if (cut < fused.size() && cut >= 1) fused.resize(cut);
  }
  if (static_cast<int>(fused.size()) > limit)
    fused.resize(static_cast<size_t>(limit));
  return fused;
}

}  // namespace qbrain::search::n46c_reference
