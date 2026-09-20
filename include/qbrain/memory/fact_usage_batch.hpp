#pragma once
// Explicit, snapshot-checked batch operations. A preview is not write permission.
// The owning route supplies apply; payloads cannot set it. No nested writers.
#include "qbrain/memory/fact_usage.hpp"
#include <map>
#include <set>

namespace qbrain::memory {
namespace usage_batch_detail {
using namespace usage_detail;
constexpr std::size_t max_items = 32;
constexpr std::size_t max_facts = 8;
constexpr std::size_t max_result_bytes = 16384;

struct Request { bool report; Json items; std::string snapshot; };
inline Request parse(const Json& payload, bool apply) {
  if (apply) keys(payload,{"operation","items","snapshot"});
  else keys(payload,{"operation","items"});
  const auto operation=field(payload,"operation");
  require(operation=="report" || operation=="revoke","fact_usage_batch_operation");
  require(payload.contains("items") && payload["items"].is_array() &&
      !payload["items"].empty() && payload["items"].size()<=max_items,"fact_usage_batch_items");
  Request request{operation=="report",Json::array(),""};
  if (apply) {request.snapshot=field(payload,"snapshot");identifier(request.snapshot);}
  std::set<std::string> ids,facts;
  for (const auto& item:payload["items"]) {
    if (request.report) keys(item,{"fact_id","usage_id","expected_revision"});
    else keys(item,{"fact_id","usage_id"});
    const auto id=field(item,"fact_id"),uid=field(item,"usage_id");
    identifier(id);identifier(uid);
    require(ids.insert(uid).second,"fact_usage_batch_duplicate_id");
    facts.insert(id);
    require(facts.size()<=max_facts,"fact_usage_batch_fact_limit");
    Json canonical={{"fact_id",id},{"usage_id",uid}};
    if (request.report) canonical["expected_revision"]=revision(item);
    request.items.push_back(std::move(canonical));
  }
  std::sort(request.items.begin(),request.items.end(),[](const Json& a,const Json& b){
    return a["usage_id"].get<std::string>()<b["usage_id"].get<std::string>();
  });
  return request;
}
struct Target { int64_t revision; std::vector<UsageEntry> entries; std::size_t additions=0; };

inline Json preview(Brain& brain,const std::string& source,const Request& request) {
  auto& db=brain.db();
  const bool initialized=usage_ready(db);
  if (!request.report) require(initialized,"fact_usage_not_found");
  std::map<std::string,Target> targets;
  Json decisions=Json::array();int changes=0;
  for (const auto& item:request.items) {
    const auto id=item["fact_id"].get<std::string>();
    const auto uid=item["usage_id"].get<std::string>();
    auto found=targets.find(id);
    if (found==targets.end()) {
      // Expired/retired records stay revocable without disclosing their quotes.
      const auto rev=request.report ? usable_fact(brain,source,id)["revision"].get<int64_t>()
                                    : stored_usage_revision(db,source,id);
      if (request.report)
        require(!archive_ready(db) || !is_archived(db,source,id),"fact_usage_archived");
      Target target{rev,initialized?usage_entries(db,source,id,rev):std::vector<UsageEntry>{},0};
      found=targets.emplace(id,std::move(target)).first;
    }
    auto& target=found->second;
    if (request.report) require(item["expected_revision"]==target.revision,"fact_revision_conflict");
    const auto existing=initialized?find_usage(db,source,uid):std::optional<UsageEntry>{};
    bool change=false;std::string action;int64_t rev=target.revision;
    Json reported=nullptr,withdrawn=nullptr;
    if (request.report) {
      if (existing) {
        require(existing->row.fact==id && existing->row.rev==rev,"fact_usage_id_conflict");
        require(!existing->row.revoked,"fact_usage_withdrawn");
        action="already_reported";reported=existing->row.at;
      } else {
        ++target.additions;
        require(target.entries.size()+target.additions<=max_use_receipts,"fact_usage_capacity");
        action="report";change=true;
      }
    } else {
      require(existing.has_value() && existing->row.fact==id,"fact_usage_not_found");
      rev=existing->row.rev;reported=existing->row.at;
      if (existing->row.revoked) {action="already_withdrawn";withdrawn=existing->row.withdrawn;}
      else {action="revoke";change=true;}
    }
    if (change) ++changes;
    decisions.push_back({{"fact_id",id},{"usage_id",uid},{"fact_revision",rev},
      {"action",action},{"will_change",change},{"reported_at",reported},{"withdrawn_at",withdrawn}});
  }
  Json state=Json::array();
  for (const auto& [id,target]:targets) {
    Json receipts=Json::array();
    for (const auto& entry:target.entries) {
      const auto& row=entry.row;
      receipts.push_back({{"usage_id",entry.uid},{"fact_revision",row.rev},
        {"reported_at",row.at},{"withdrawn_at",row.revoked?Json(row.withdrawn):Json(nullptr)}});
    }
    state.push_back({{"fact_id",id},{"revision",target.revision},{"receipts",std::move(receipts)}});
  }
  // Absence and an empty valid module have equal logical receipt state. This
  // allows separate first-write initialization without weakening selected-row
  // binding. Bad module metadata still fails above. This hash is not a secret.
  const auto operation=request.report?"report":"revoke";
  const Json binding={{"schema","qbrain-usage-batch-snapshot-v1"},{"source_id",source},
    {"operation",operation},{"items",request.items},{"facts",std::move(state)}};
  auto out=usage_flags();
  out.update({{"view","usage_batch"},{"operation",operation},{"source_id",source},
    {"applied",false},{"atomic",true},{"snapshot",util::sha256_hex(binding.dump())},
    {"changed",0},{"would_change",changes},{"unchanged",request.items.size()-changes},
    {"items",std::move(decisions)}});
  require(out.dump().size()+1<=max_result_bytes,"fact_usage_batch_result_limit");
  return out;
}
} // namespace usage_batch_detail

inline Json usage_batch(Brain& brain,const std::string& source,const Json& payload,bool apply=false) {
  using namespace usage_batch_detail;
  FactStore eligibility(brain,source); // Existing backend/source validation.
  const auto request=parse(payload,apply);auto& db=brain.db();Json planned;
  // Never initialize a module or own a transaction inside the caller's one.
  // Autocommit alone misses implicit transactions held by unfinished SELECT,
  // RETURNING or blob handles. Never commit/roll back a caller-owned snapshot
  // or pending write, including one in an attached database.
  if (apply) require(sqlite3_get_autocommit(db.handle())!=0 &&
      sqlite3_txn_state(db.handle(),nullptr)==SQLITE_TXN_NONE,"fact_transaction_active");
  {
    ReadSnapshot snapshot(db);
    planned=preview(brain,source,request);
    if (apply) require(planned["snapshot"]==request.snapshot,"fact_usage_batch_snapshot_conflict");
  }
  if (!apply) return planned;
  if (request.report && planned["would_change"].get<int>()>0) initialize_usage(db);
  Tx tx(db);usage_foreign_keys(db);
  planned=preview(brain,source,request);
  require(planned["snapshot"]==request.snapshot,"fact_usage_batch_snapshot_conflict");
  const auto now=clock_now();
  require(now>=0,"fact_usage_invalid_metadata");
  for (auto& item:planned["items"]) {
    if (!item["will_change"].get<bool>()) continue;
    const auto id=item["fact_id"].get<std::string>(),uid=item["usage_id"].get<std::string>();
    if (request.report) {
      auto s=db.prepare("INSERT INTO memory_fact_usage(source_id,usage_id,fact_id,fact_revision,reported_at) VALUES(?,?,?,?,?)");
      s.bind_text(1,source);s.bind_text(2,uid);s.bind_text(3,id);
      s.bind_int(4,item["fact_revision"].get<int64_t>());s.bind_int(5,now);s.step_done();
      require(db.changes()==1,"fact_usage_write_conflict");
      item["reported_at"]=now;
    } else {
      const auto at=std::max(now,item["reported_at"].get<int64_t>());
      auto s=db.prepare("UPDATE memory_fact_usage SET withdrawn_at=? WHERE source_id=? AND usage_id=? AND fact_id=? AND withdrawn_at IS NULL");
      s.bind_int(1,at);s.bind_text(2,source);s.bind_text(3,uid);s.bind_text(4,id);s.step_done();
      require(db.changes()==1,"fact_usage_write_conflict");
      item["withdrawn_at"]=at;
    }
  }
  planned["applied"]=true;planned["changed"]=planned["would_change"];
  require(planned.dump().size()+1<=max_result_bytes,"fact_usage_batch_result_limit");
  tx.commit();return planned;
}
} // namespace qbrain::memory
