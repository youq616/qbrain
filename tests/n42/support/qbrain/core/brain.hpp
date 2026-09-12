#pragma once
// TEST ADAPTER ONLY. It executes real SQLite statements but is NOT the
// production storage backend, migration layer, authorization or provider code.
#include "qbrain/core/types.hpp"
#include <sqlite3.h>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <utility>
namespace qbrain {
class N42Database {
  sqlite3* db_ = nullptr;
 public:
  bool force_fts_failure = false;
  N42Database() {
    if(sqlite3_open(":memory:",&db_)!=SQLITE_OK) throw std::runtime_error("SQLite open failed");
  }
  ~N42Database(){if(db_)sqlite3_close(db_);}
  N42Database(const N42Database&)=delete;
  N42Database& operator=(const N42Database&)=delete;
  void exec(const char* sql){if(sqlite3_exec(db_,sql,nullptr,nullptr,nullptr)!=SQLITE_OK)throw std::runtime_error(sqlite3_errmsg(db_));}
  class Statement {
    sqlite3_stmt* p_=nullptr;
    void checked(int rc){if(rc!=SQLITE_OK)throw std::runtime_error("SQLite bind failed");}
   public:
    Statement(sqlite3* db,std::string_view sql){
      if(sqlite3_prepare_v2(db,sql.data(),static_cast<int>(sql.size()),&p_,nullptr)!=SQLITE_OK)
        throw std::runtime_error(sqlite3_errmsg(db));
    }
    ~Statement(){if(p_)sqlite3_finalize(p_);}
    Statement(const Statement&)=delete;
    Statement& operator=(const Statement&)=delete;
    Statement(Statement&&o)noexcept:p_(std::exchange(o.p_,nullptr)){}
    void bind_null(int i){checked(sqlite3_bind_null(p_,i));}
    void bind_int(int i,int64_t v){checked(sqlite3_bind_int64(p_,i,v));}
    void bind_text(int i,std::string_view v){checked(sqlite3_bind_text(p_,i,v.data(),static_cast<int>(v.size()),SQLITE_TRANSIENT));}
    void bind_blob(int i,const void* p,int n){checked(sqlite3_bind_blob(p_,i,p,n,SQLITE_TRANSIENT));}
    bool step(){auto rc=sqlite3_step(p_);if(rc==SQLITE_ROW)return true;if(rc==SQLITE_DONE)return false;throw std::runtime_error(sqlite3_errmsg(sqlite3_db_handle(p_)));}
    int64_t column_int(int i){return sqlite3_column_int64(p_,i);}
    double column_double(int i){return sqlite3_column_double(p_,i);}
    std::string column_text(int i){auto p=sqlite3_column_text(p_,i);return p?std::string(reinterpret_cast<const char*>(p),static_cast<size_t>(sqlite3_column_bytes(p_,i))):std::string{};}
    std::vector<uint8_t> column_blob(int i){auto p=static_cast<const uint8_t*>(sqlite3_column_blob(p_,i));auto n=sqlite3_column_bytes(p_,i);return n?std::vector<uint8_t>(p,p+n):std::vector<uint8_t>{};}
  };
  Statement prepare(std::string_view s){return Statement(db_,s);}
  struct FtsRow {int64_t page_id;std::string slug,title,type,snippet;double rank;};
  std::vector<FtsRow> fts_search(const std::string&q,int limit,const std::string&source){
    if(force_fts_failure)throw std::runtime_error("deliberate test fallback");
    std::string sql="SELECT p.id,p.slug,p.title,p.type,snippet(page_fts,1,'','','',32),bm25(page_fts) FROM page_fts JOIN pages p ON p.id=page_fts.rowid WHERE page_fts MATCH ? AND p.deleted_at IS NULL";
    if(!source.empty())sql+=" AND p.source_id=?";
    sql+=" ORDER BY bm25(page_fts),p.id LIMIT ?";
    auto st=prepare(sql);st.bind_text(1,q);int ix=2;if(!source.empty())st.bind_text(ix++,source);st.bind_int(ix,limit);
    std::vector<FtsRow> out;
    while(st.step())out.push_back({st.column_int(0),st.column_text(1),st.column_text(2),st.column_text(3),st.column_text(4),st.column_double(5)});
    return out;
  }
};
class Brain {
  N42Database db_;
  Config config_;
 public:
  static std::optional<std::string> canonical_source_id(const std::string& source_id) {
  if (source_id.empty() || source_id.size() > 64) return std::nullopt;
  std::string canon;
  canon.reserve(source_id.size());
  for (unsigned char c : source_id) {
    if (c >= 'A' && c <= 'Z') {
      canon.push_back(static_cast<char>(c - 'A' + 'a'));
    } else if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-') {
      canon.push_back(static_cast<char>(c));
    } else {
      return std::nullopt;
    }
  }
  static const char* kReserved[] = {"con",  "prn",  "aux",  "nul",  "com1", "com2", "com3",
                                    "com4", "com5", "com6", "com7", "com8", "com9", "lpt1",
                                    "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8",
                                    "lpt9"};
  for (auto* reserved : kReserved) {
    if (canon == reserved) return std::nullopt;
  }
  return canon;
  }
  Config& config(){return config_;}
  N42Database& db(){return db_;}
  std::vector<Link> get_links_to(const std::string&slug,const std::string&source){
    auto st=db_.prepare("SELECT from_slug FROM links WHERE to_slug=? AND source_id=?");
    st.bind_text(1,slug);st.bind_text(2,source);std::vector<Link> out;
    while(st.step()){Link l;l.source_id=source;l.from_slug=st.column_text(0);l.to_slug=slug;out.push_back(l);}return out;
  }
};
inline std::string resolve_api_key(const Config&,bool){return {};}
}
