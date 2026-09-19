#pragma once
// Bounded, read-only receipt discovery. A snapshot hash detects changed current
// metadata; it is not a held transaction, authorization or proof of real use.
#include "qbrain/memory/fact_usage.hpp"
#include <vector>

namespace qbrain::memory {
inline Json read_usage_receipts(Brain& brain,const std::string& source,
    const std::string& id,const std::string& state="all",const std::string& after="",
    const std::string& snapshot="",int limit=10,int max_bytes=8192) {
  using namespace usage_detail;
  identifier(id);
  require(state=="all" || state=="current" || state=="historical" || state=="withdrawn",
          "fact_usage_invalid_filter");
  require(limit>=1 && limit<=50,"fact_invalid_limit");
  require(max_bytes>=512 && max_bytes<=32768,"fact_invalid_byte_limit");
  require(after.empty()==snapshot.empty(),"fact_usage_cursor_pair_required");
  if(!after.empty()){identifier(after);identifier(snapshot);}
  FactStore eligibility(brain,source); // Existing backend/source validation.
  auto& db=brain.db();ReadSnapshot read_snapshot(db);
  const auto fact=usable_fact(brain,source,id);
  const auto revision=fact["revision"].get<int64_t>();
  const bool initialized=usage_ready(db);
  const bool archived=archive_ready(db) && is_archived(db,source,id);
  Json all=Json::array();
  if(initialized) {
    auto rows=db.prepare(std::string("SELECT ")+usage_columns+
      ",usage_id,typeof(usage_id),typeof(fact_id) FROM memory_fact_usage "
      "WHERE source_id=? AND fact_id=? ORDER BY usage_id LIMIT 4097");
    rows.bind_text(1,source);rows.bind_text(2,id);
    std::string previous;
    while(rows.step()) {
      require(all.size()<max_use_receipts,"fact_usage_invalid_metadata");
      const auto row=usage_row(rows);const auto uid=rows.column_text(7);
      identifier(uid);
      require(rows.column_text(8)=="text" && rows.column_text(9)=="text" &&
              row.fact==id && row.rev<=revision && (previous.empty() || uid>previous),
              "fact_usage_invalid_metadata");
      previous=uid;
      all.push_back({{"usage_id",uid},{"fact_revision",row.rev},{"reported_at",row.at},
        {"withdrawn_at",row.revoked?Json(row.withdrawn):Json(nullptr)},
        {"state",row.revoked?"withdrawn":row.rev==revision?"current":"historical"}});
    }
  }
  // Validate and hash the complete bounded set BEFORE filtering/page selection;
  // a changed or corrupt off-page row cannot silently alter a paged audit.
  const Json binding={{"schema","qbrain-usage-snapshot-v1"},{"source_id",source},
    {"fact_id",id},{"fact_revision",revision},{"initialized",initialized},
    {"archived",archived},{"receipt_state",state},{"receipts",all}};
  const auto token=util::sha256_hex(binding.dump());
  if(!snapshot.empty())require(snapshot==token,"fact_usage_snapshot_conflict");
  std::vector<std::size_t> selected;
  for(std::size_t i=0;i<all.size();++i)
    if(state=="all" || all[i]["state"]==state)selected.push_back(i);
  std::size_t start=0;
  if(!after.empty()) {
    auto found=std::find_if(selected.begin(),selected.end(),[&](std::size_t i){return all[i]["usage_id"]==after;});
    require(found!=selected.end(),"fact_usage_cursor_invalid");
    start=static_cast<std::size_t>(found-selected.begin())+1;
  }
  auto out=usage_flags();
  out.update({{"view","usage_receipts"},{"source_id",source},{"fact_id",id},
    {"fact_revision",revision},{"initialized",initialized},{"archived",archived},
    {"receipt_state",state},{"snapshot",token},{"matched_receipts",selected.size()},
    {"items",Json::array()},{"has_more",false},{"next_after_id",nullptr}});
  const auto fits=[&](){return out.dump().size()+1<=static_cast<std::size_t>(max_bytes);};
  require(fits(),"fact_usage_byte_budget");
  std::size_t next=start;
  while(next<selected.size() && out["items"].size()<static_cast<std::size_t>(limit)) {
    out["items"].push_back(all[selected[next]]);
    out["has_more"]=next+1<selected.size();
    out["next_after_id"]=out["has_more"].get<bool>()?out["items"].back()["usage_id"]:Json(nullptr);
    if(!fits()) {out["items"].erase(out["items"].end()-1);break;}
    ++next;
  }
  require(next>start || start==selected.size(),"fact_usage_byte_budget");
  out["has_more"]=next<selected.size();
  out["next_after_id"]=out["has_more"].get<bool>()?out["items"].back()["usage_id"]:Json(nullptr);
  require(fits(),"fact_usage_byte_budget");
  return out;
}
} // namespace qbrain::memory
