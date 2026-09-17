#include "qbrain/integration/diagnostics.hpp"
#include "qbrain/integration/hook.hpp"
#include "qbrain/cli/app.hpp"
#include "qbrain/memory/session_memory.hpp"
#include "qbrain/util/hash.hpp"
#include <map>
#include <set>
#include "qbrain/core/brain.hpp"
#include "qbrain/ops/registry.hpp"
#include "qbrain/ingest/import.hpp"
#include "qbrain/ingest/chunker.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/cycle/dream.hpp"
#include "qbrain/jobs/minions.hpp"
#include "qbrain/mcp/server.hpp"
#include "qbrain/service/inbox_watch.hpp"
#include "qbrain/service/live_sync.hpp"
#include "qbrain/util/paths.hpp"
#include "qbrain/util/string_util.hpp"
#include "qbrain/util/time_util.hpp"
#include "qbrain/util/log.hpp"
#include "qbrain/version.hpp"
#include <fstream>
#include <iostream>
#include <sstream>
#include <functional>
#include <algorithm>
#include <charconv>
#include <cstdlib>
#include <nlohmann/json.hpp>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#define Sleep(ms) usleep((ms) * 1000)
#endif

namespace qbrain::cli {
namespace {

}  // namespace

std::string resolve_brain_id(const std::vector<std::string>& args) {
  for (size_t i = 0; i + 1 < args.size(); ++i) {
    if (args[i] == "--brain") return util::normalize_brain_id(args[i + 1]);
  }
  if (const char* e = std::getenv("QBRAIN_BRAIN")) {
    if (*e) return util::normalize_brain_id(e);
  }
  auto c = load_file_config();
  return c.brain_id.empty() ? "default" : util::normalize_brain_id(c.brain_id);
}

namespace {

std::string brain_id_from_args(const std::vector<std::string>& args) { return resolve_brain_id(args); }

}  // namespace

// N30 D6: strict numeric parsing for TCP port options. Accepts decimal digits
// only (no sign, whitespace, or trailing characters) and enforces the valid
// port range 1-65535. Defined with external linkage so the unit suite can
// exercise it without a public CLI header.
bool parse_port_value(const std::string& text, int& out) {
  if (text.empty()) return false;
  int value = 0;
  const char* first = text.data();
  const char* last = text.data() + text.size();
  const auto parsed = std::from_chars(first, last, value);
  if (parsed.ec != std::errc{} || parsed.ptr != last) return false;
  if (value < 1 || value > 65535) return false;
  out = value;
  return true;
}

namespace {

bool flag(const std::vector<std::string>& args, const std::string& name) {
  for (auto& a : args)
    if (a == name) return true;
  return false;
}

nlohmann::json operation_json(const ops::OpResult& result) {
  auto parsed = nlohmann::json::parse(result.json, nullptr, false);
  if (!parsed.is_discarded()) return parsed;
  return {{"error",
           {{"code", "invalid_operation_result"},
            {"message", "operation returned invalid JSON"}}}};
}

std::string opt(const std::vector<std::string>& args, const std::string& name,
                const std::string& def = {}) {
  for (size_t i = 0; i + 1 < args.size(); ++i) {
    if (args[i] == name) return args[i + 1];
  }
  return def;
}

std::string join_positional(const std::vector<std::string>& args,
                            const std::vector<std::string>& skip_flags) {
  std::string out;
  for (size_t i = 0; i < args.size(); ++i) {
    bool is_flag = false;
    for (auto& f : skip_flags) {
      if (args[i] == f) {
        is_flag = true;
        if (f.rfind("--", 0) == 0 && f != "--json" && f != "--save" && f != "--stdin" &&
            f != "--all" && f != "--help" && f != "--no-vector" && f != "--rerank" &&
            f != "--rerank-llm" && f != "--apply" && f != "--once" && f != "--watch")
          ++i;
        break;
      }
    }
    if (is_flag) continue;
    if (args[i].rfind("--", 0) == 0) continue;
    if (!out.empty()) out.push_back(' ');
    out += args[i];
  }
  return util::trim(out);
}

void print_help() {
  std::cout <<
      "Qbrain — Windows-native personal knowledge brain (C++)\n\n"
      "Usage:\n"
      "  qbrain <command> [args]\n\n"
      "Commands:\n"
      "  init [--brain id]              Create local brain (SQLite, no WSL)\n"
      "  doctor [--remediate] [--json]   Health check; --remediate auto-fixes\n"
      "  config get|set <key> [value]   Configuration\n"
      "  put --slug s --title t [--file f] [--type note]\n"
      "  get <slug>\n"
      "  list [--limit N] [--type t]\n"
      "  capture \"text\" | --file f | --stdin\n"
      "  import <path>\n"
      "  search \"query\" [--limit N] [--json] [--no-vector] [--mode m] [--rerank]\n"
      "  think \"question\" [--json] [--save]\n"
      "  graph <slug> [--depth N]\n"
      "  delete <slug> [--source default]\n"
      "  embed --all | --slug s | --drain   (drain: process embed jobs queue)\n"
      "  context list|read|summary [--uri qbrain://source/resources/] [--layer L0|L1|L2]\n"
      "  hook diagnostics --config <absolute config> [--event <event>] [--session-key <hex>] (read only)\n"
      "  hook --config <absolute project config> (JSON stdin; fail-open)\n"
      "  serve [--brain id] [--tool-profile full|memory] [--allow-write] [--http] [--port N]\n"
      "  inbox [--watch]                     process %LOCALAPPDATA%\\Qbrain\\inbox\n"
      "  sync <notes-dir> [--watch] [--once]  live-sync notes (mtime state)\n"
      "  worker [--once]                     claim/complete minion jobs + inbox\n"
      "  dream [--apply] [--phase p] [--retention-hours N] [--json]\n"
      "  fact create|read|attach|retract|supersede|contradict [--source id] (writes read JSON stdin)\n"
      "  fact archive|restore [--source id] (JSON stdin: fact_id, expected_revision)\n"
      "  fact batch-preview|batch-apply [--source id] (JSON stdin: operation, items)\n"
      "  fact candidates --operation archive|restore [--after-id ID] [--predicate KEY] [--stale-after-days N] [--limit N] [--max-bytes N]\n"
      "  fact lifecycle [--id ID] [--predicate KEY] [--stale-after-days N] [--limit N] [--max-bytes N]\n"
      "  fact conflicts [--source id] [--id ID] [--predicate NAME] [--limit N] [--max-bytes N]\n"
      "  fact promote --event ID [--source id]  (local extracted event; complete quotes, no model)\n"
      "  fact recall --query <text> [--match literal|all_terms|any_terms] [--predicate KEY] [--limit N] [--max-bytes N] [--source id]\n"
      "  memory capture|extract|drain|read|status|forget [--source id]\n"
      "  session-capture [--automatic] [--session-id id] [--fragment-id id]\n"
      "  version\n"
      "  help\n\n"
      "MCP:\n"
      "  claude mcp add qbrain -- qbrain serve\n"
      "  claude mcp add qbrain -- qbrain serve --allow-write\n"
      "  HTTP: set QBRAIN_MCP_TOKEN then qbrain serve --http --port 7420\n\n"
      "Data: %LOCALAPPDATA%\\Qbrain\\\n";
}

int cmd_init(const std::vector<std::string>& args) {
  auto id = brain_id_from_args(args);
  util::ensure_dir(util::qbrain_root());
  util::ensure_dir(util::brain_dir(id));
  util::ensure_dir(util::audit_dir());
  Brain b(id);
  b.open();
  auto cfg = load_file_config();
  cfg.brain_id = id;
  if (!flag(args, "--no-default")) save_file_config(cfg);
  std::cout << "Initialized brain '" << id << "' at "
            << util::path_to_utf8(util::brain_db_path(id)) << "\n";
  return 0;
}

int with_brain(const std::vector<std::string>& args,
               const std::function<int(Brain&)>& fn) {
  Brain b(brain_id_from_args(args));
  try {
    b.open();
  } catch (const std::exception& e) {
    std::cerr << "open brain failed: " << e.what() << "\nRun: qbrain init\n";
    return 2;
  }
  return fn(b);
}

int cmd_doctor(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.remote = false;
    ctx.allow_write = true;
    if (flag(args, "--remediate")) {
      auto r = ops::global_registry().call("doctor_remediate", ctx);
      auto h = ops::global_registry().call("run_doctor", ctx);
      if (flag(args, "--json")) {
        nlohmann::json envelope = {{"ok", r.ok && h.ok},
                                   {"remediation", operation_json(r)},
                                   {"health", operation_json(h)}};
        std::cout << envelope.dump(2) << "\n";
        return r.ok && h.ok ? 0 : 1;
      }
      std::cout << r.text;
      if (!r.ok) return 1;
      std::cout << h.text;
      return h.ok ? 0 : 1;
    }
    auto r = ops::global_registry().call("run_doctor", ctx);
    if (flag(args, "--json"))
      std::cout << r.json << "\n";
    else
      std::cout << r.text;
    return r.ok ? 0 : 1;
  });
}

int cmd_config(const std::vector<std::string>& args) {
  if (args.size() < 2) {
    std::cerr << "usage: qbrain config get|set <key> [value] [--local]\n";
    return 1;
  }
  return with_brain(args, [&](Brain& b) {
    // args = [get|set, key, value?]
    if (args[0] == "get") {
      if (args.size() < 2) return 1;
      const auto& key = args[1];
      auto v = b.get_config_value(key);
      if (!v) {
        auto c = b.config();
        if (key == "embedding.model") std::cout << c.embedding_model << "\n";
        else if (key == "embedding.base_url") std::cout << c.embedding_base_url << "\n";
        else if (key == "embedding.dimensions") std::cout << c.embedding_dimensions << "\n";
        else if (key == "chat.model") std::cout << c.chat_model << "\n";
        else if (key == "chat.base_url") std::cout << c.chat_base_url << "\n";
        else if (key == "embedding.api_key" || key == "chat.api_key") {
          // never print secrets; only presence
          std::cout << "(not in db; check env OPENAI_API_KEY / QBRAIN_API_KEY)\n";
          return 0;
        } else {
          std::cerr << "not set\n";
          return 1;
        }
        return 0;
      }
      if (key.find("api_key") != std::string::npos) {
        std::cout << "(set, " << v->size() << " chars)\n";
        return 0;
      }
      std::cout << *v << "\n";
      return 0;
    }
    if (args[0] == "set") {
      if (args.size() < 3) return 1;
      b.save_config_value(args[1], args[2], !flag(args, "--local"));
      std::cout << "set " << args[1] << "\n";
      return 0;
    }
    return 1;
  });
}

int cmd_put(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["slug"] = opt(args, "--slug");
    ctx.args["title"] = opt(args, "--title", ctx.args["slug"]);
    ctx.args["type"] = opt(args, "--type", "note");
    auto file = opt(args, "--file");
    if (!file.empty()) {
      std::ifstream in(util::utf8_to_path(file), std::ios::binary);
      std::ostringstream ss;
      ss << in.rdbuf();
      ctx.args["body"] = ss.str();
    } else {
      ctx.args["body"] = opt(args, "--body");
    }
    auto r = ops::global_registry().call("put_page", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text) << "\n";
    return r.ok ? 0 : r.exit_code;
  });
}

int cmd_get(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["slug"] = join_positional(args, {"--brain", "--json", "--source"});
    auto r = ops::global_registry().call("get_page", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text);
    return r.ok ? 0 : r.exit_code;
  });
}

int cmd_list(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["limit"] = opt(args, "--limit", "50");
    ctx.args["type"] = opt(args, "--type");
    auto r = ops::global_registry().call("list_pages", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text);
    return 0;
  });
}

int cmd_capture(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    std::string text;
    if (flag(args, "--stdin")) {
      std::ostringstream ss;
      ss << std::cin.rdbuf();
      text = ss.str();
    } else if (!opt(args, "--file").empty()) {
      std::ifstream in(util::utf8_to_path(opt(args, "--file")), std::ios::binary);
      std::ostringstream ss;
      ss << in.rdbuf();
      text = ss.str();
    } else {
      text = join_positional(args, {"--brain", "--file", "--stdin", "--type", "--json"});
    }
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["text"] = text;
    ctx.args["type"] = opt(args, "--type", "note");
    auto r = ops::global_registry().call("capture", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text) << "\n";
    return r.ok ? 0 : r.exit_code;
  });
}

int cmd_import(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    auto path = join_positional(args, {"--brain", "--json"});
    if (path.empty()) {
      std::cerr << "usage: qbrain import <path>\n";
      return 1;
    }
    auto r = ingest::import_path(b, path);
    std::cout << "import files=" << r.files << " pages=" << r.pages << " link_refs=" << r.links
              << " errors=" << r.errors << "\n";
    return r.errors ? 1 : 0;
  });
}

// Read raw UTF-8 bytes; unlike operator>>/PowerShell's text pipeline this preserves JSON exactly.
std::string bounded_stdin() {
  std::string value; char buffer[4096];
  while (std::cin.read(buffer,sizeof(buffer)) || std::cin.gcount()) {
    value.append(buffer,static_cast<size_t>(std::cin.gcount()));
    if (value.size()>memory::max_payload_bytes) throw memory::Error("payload_too_large");
  }
  if (std::cin.bad()) throw memory::Error("stdin_read_failed");
  if (value.rfind("\xEF\xBB\xBF",0)==0) value.erase(0,3);
  return value;
}
int cmd_memory(const std::vector<std::string>& args) {
  if(args.empty()) { std::cerr << "usage: qbrain memory capture|extract|drain|read|status|forget\n"; return 1; }
  const auto& action = args[0];
  std::set<std::string> values={"--brain","--source"};
  std::set<std::string> flags;
  if(action=="capture") { flags={"--manual","--stdin"}; }
  else if(action=="drain") { values.insert("--method"); }
  else if(action=="extract") { values.insert("--event"); values.insert("--method"); }
  else if(action=="forget" || action=="status") { values.insert("--event"); }
  else if(action=="read") { values.insert("--query"); values.insert("--limit"); values.insert("--max-bytes"); }
  else throw memory::Error("invalid_action");
  std::set<std::string> seen;
  for(std::size_t i=1;i<args.size();++i) {
    if(!seen.insert(args[i]).second) throw memory::Error("duplicate_argument");
    if(flags.count(args[i])) continue;
    if(!values.count(args[i]) || i+1>=args.size()) throw memory::Error("invalid_cli_argument");
    ++i;
  }
  if((action=="extract" || action=="forget" || action=="status") && opt(args,"--event").empty())
    throw memory::Error("event_id_required");
  return with_brain(args,[&](Brain& b) {
    if(action=="drain") { std::cout << memory::drain(b,opt(args,"--source","default"),opt(args,"--method","local")).dump() << "\n"; return 0; }
    ops::OpContext ctx; ctx.brain=&b;
    ctx.args["source_id"]=opt(args,"--source","default");
    const auto& action=args[0];
    const bool reading=action=="read" || action=="status";
    if(reading) {
      ctx.args["query"]=opt(args,"--query"); ctx.args["limit"]=opt(args,"--limit","10");
      ctx.args["max_bytes"]=opt(args,"--max-bytes","8192");
      if(action=="status") ctx.args["event_id"]=opt(args,"--event");
    } else {
      ctx.args["action"]=action;
      if(action=="capture") {
        ctx.args["payload"]=bounded_stdin();
        if(flag(args,"--manual")) ctx.args["manual"]="true";
      } else {
        ctx.args["event_id"]=opt(args,"--event");
        if(action=="extract") ctx.args["method"]=opt(args,"--method","local");
      }
    }
    auto r=ops::global_registry().call(reading?"memory_read":"memory_write",ctx);
    std::cout << r.json << "\n"; return r.ok?0:1;
  });
}
// Facts use existing operation authorization and source resolution, not a new bypass.
int cmd_fact(const std::vector<std::string>& args) {
  try {
    if(args.empty()) throw memory::Error("fact_action_required");
    const auto& action=args[0];
    const bool promoting=action=="promote";
    const bool conflicts=action=="conflicts";
    const bool recall=action=="recall";
    const bool lifecycle=action=="lifecycle";
    const bool candidates=action=="candidates";
    const bool batch_preview=action=="batch-preview";
    const bool batch_apply=action=="batch-apply";
    const bool batch=batch_preview || batch_apply;
    const bool reading=action=="read" || conflicts || recall || lifecycle || candidates || batch_preview;
    if(!reading && !promoting && !batch_apply && action!="create" && action!="attach" && action!="retract" &&
       action!="supersede" && action!="contradict" && action!="archive" && action!="restore") throw memory::Error("invalid_action");
    std::set<std::string> values={"--brain","--source"},flags;
    if(batch) flags.insert("--stdin");
    else if(reading) {
      values.insert({"--predicate","--limit","--max-bytes"});
      if(candidates)values.insert({"--operation","--after-id"});
      else values.insert(recall?"--query":"--id");
      if(recall) values.insert("--match");
      if(lifecycle || candidates) values.insert("--stale-after-days");
      if(!conflicts && !recall && !lifecycle && !candidates) flags.insert("--history");
    }
    else if(promoting) values.insert("--event");
    else flags.insert("--stdin");
    std::set<std::string> seen;
    std::map<std::string,std::string> parsed;
    for(std::size_t i=1;i<args.size();++i) {
      if(!seen.insert(args[i]).second) throw memory::Error("duplicate_argument");
      if(flags.count(args[i])) continue;
      if(!values.count(args[i]) || i+1>=args.size()) throw memory::Error("invalid_cli_argument");
      parsed.emplace(args[i],args[i+1]);
      ++i;
    }
    // Consume only option positions validated above. A literal query such as
    // "--match" or "--brain" is data, never a second option during lookup.
    const auto value=[&](const std::string& key,const std::string& fallback=std::string{}) {
      const auto it=parsed.find(key);return it==parsed.end()?fallback:it->second;
    };
    std::vector<std::string> brain_args;
    if(parsed.count("--brain")) brain_args={"--brain",value("--brain")};
    return with_brain(brain_args,[&](Brain& b) {
      ops::OpContext c; c.brain=&b; c.args["source_id"]=value("--source","default");
      if(batch) {
        c.args["payload"]=bounded_stdin();
        if(batch_preview)c.args["view"]="lifecycle_batch";
        else c.args["action"]="fact_lifecycle_batch";
      } else if(reading) {
        c.args["view"]=candidates?"lifecycle_candidates":lifecycle?"lifecycle":(recall?"recall":(conflicts?"conflicts":"facts"));
        if(candidates) {c.args["operation"]=value("--operation");c.args["after_id"]=value("--after-id");}
        else if(recall) { c.args["query"]=value("--query"); c.args["match"]=value("--match","literal"); }
        else c.args["fact_id"]=value("--id");
        c.args["predicate"]=value("--predicate"); c.args["limit"]=value("--limit","10");
        c.args["max_bytes"]=value("--max-bytes","8192");
        if(lifecycle || candidates) c.args["stale_after_days"]=value("--stale-after-days","180");
        if(!conflicts && !recall && !lifecycle && !candidates) c.args["include_history"]=seen.count("--history")?"true":"false";
      } else if(promoting) {
        c.args["action"]="fact_promote";c.args["event_id"]=value("--event");
      } else { c.args["action"]="fact_"+action; c.args["payload"]=bounded_stdin(); }
      const auto result=ops::global_registry().call(reading?"memory_read":"memory_write",c);
      std::cout<<result.json<<"\n"; return result.ok?0:1;
    });
  } catch(const memory::Error& e) {
    std::cout<<nlohmann::json({{"error",{{"code",e.what()}}}}).dump()<<"\n"; return 1;
  }
}
// Legacy raw transcripts have unknown speaker attribution and cannot become user facts.
int cmd_session_capture(const std::vector<std::string>& args) {
  return with_brain(args,[&](Brain& b) {
    const auto body=bounded_stdin();
    const auto label=opt(args,"--label","session");
    const auto session=opt(args,"--session-id","legacy-"+util::sha256_hex(label));
    const auto fragment=opt(args,"--fragment-id",util::sha256_hex(body));
    const nlohmann::json payload={{"session_id",session},{"fragment_id",fragment},
      {"messages",nlohmann::json::array({{{"role","unknown"},{"content",body}}})}};
    ops::OpContext ctx; ctx.brain=&b; ctx.args={{"source_id",opt(args,"--source","default")},
      {"action","capture"},{"payload",payload.dump()},{"manual",flag(args,"--automatic")?"false":"true"}};
    auto r=ops::global_registry().call("memory_write",ctx); std::cout << r.json << "\n"; return r.ok?0:1;
  });
}

int cmd_context(const std::vector<std::string>& args) {
  try {
    if(args.empty()||(args[0]!="list"&&args[0]!="read"&&args[0]!="summary"))throw memory::Error("invalid_context_action");
    const bool write=args[0]=="summary";
    const std::set<std::string> allowed=write?std::set<std::string>{"--brain","--source","--uri","--method"}:
      std::set<std::string>{"--brain","--source","--uri","--layer","--max-bytes","--offset","--revision"};
    std::set<std::string> seen;
    for(std::size_t i=1;i<args.size();i+=2)if(!allowed.count(args[i])||!seen.insert(args[i]).second||i+1>=args.size())throw memory::Error("invalid_cli_argument");
    return with_brain(args,[&](Brain& b){ops::OpContext c;c.brain=&b;c.args["source_id"]=opt(args,"--source","default");
      for(const auto& [flag,key]:std::vector<std::pair<std::string,std::string>>{{"--uri","uri"},{"--layer","layer"},{"--max-bytes","max_bytes"},{"--offset","offset"},{"--revision","revision"},{"--method","method"}})
        if(seen.count(flag))c.args[key]=opt(args,flag);
      auto result=ops::global_registry().call(write?"context_write":"context_read",c);std::cout<<result.json<<"\n";return result.ok?0:1;});
  }catch(const memory::Error& e){std::cout<<nlohmann::json({{"error",{{"code",e.what()}}}}).dump()<<"\n";return 1;}
}

int cmd_search(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["query"] =
        join_positional(args, {"--brain", "--limit", "--json", "--no-vector", "--mode", "--rerank",
                               "--rerank-llm"});
    ctx.args["limit"] = opt(args, "--limit", std::to_string(b.config().search_default_limit));
    if (flag(args, "--no-vector")) ctx.args["no_vector"] = "1";
    auto mode = opt(args, "--mode");
    if (!mode.empty()) ctx.args["mode"] = mode;
    if (flag(args, "--rerank")) ctx.args["rerank"] = "1";
    if (flag(args, "--rerank-llm")) ctx.args["rerank_llm"] = "1";
    auto r = ops::global_registry().call("search", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text);
    return r.ok ? 0 : r.exit_code;
  });
}

int cmd_think(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["question"] = join_positional(args, {"--brain", "--json", "--save", "--limit"});
    ctx.args["limit"] = opt(args, "--limit", "8");
    if (flag(args, "--save")) ctx.args["save"] = "1";
    auto r = ops::global_registry().call("think", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text);
    return r.ok ? 0 : r.exit_code;
  });
}

int cmd_graph(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    ops::OpContext ctx;
    ctx.brain = &b;
    ctx.args["slug"] = join_positional(args, {"--brain", "--depth", "--json"});
    ctx.args["depth"] = opt(args, "--depth", "1");
    auto r = ops::global_registry().call("get_links", ctx);
    std::cout << (flag(args, "--json") ? r.json : r.text);
    return 0;
  });
}

int cmd_serve(const std::vector<std::string>& args) {
  mcp::ServeOptions opts;
  opts.brain_id = brain_id_from_args(args);
  opts.tool_profile = opt(args,"--tool-profile","full");
  if(opts.tool_profile!="full" && opts.tool_profile!="memory") throw memory::Error("invalid_tool_profile");
  opts.allow_write = flag(args, "--allow-write");
  if (const char* e = std::getenv("QBRAIN_MCP_ALLOW_WRITE")) {
    if (std::string(e) == "1" || std::string(e) == "true") opts.allow_write = true;
  }
  Brain b(opts.brain_id);
  try {
    b.open();
  } catch (const std::exception& e) {
    std::cerr << "open brain failed: " << e.what() << "\nRun: qbrain init\n";
    return 2;
  }
  if (flag(args, "--http")) {
    const char* tok = std::getenv("QBRAIN_MCP_TOKEN");
    if (!tok || !*tok) {
      std::cerr << "QBRAIN_MCP_TOKEN env required for --http (do not pass token on argv)\n";
      return 2;
    }
    int port = 7420;
    auto ps = opt(args, "--port");
    if (ps.empty()) {
      // also accept the single-token --port=N form
      for (auto& a : args) {
        if (a.rfind("--port=", 0) == 0) {
          ps = a.substr(std::string("--port=").size());
          break;
        }
      }
    }
    if (!ps.empty() && !parse_port_value(ps, port)) {
      std::cerr << "invalid --port value (expected an integer in 1-65535)\n";
      return 2;
    }
    return mcp::run_http_server(b, opts, tok, port);
  }
  return mcp::run_stdio_server(b, opts);
}

int cmd_inbox(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    if (flag(args, "--watch")) {
      std::cout << "watching " << qbrain::util::path_to_utf8(service::inbox_dir()) << " (Ctrl+C to stop)\n";
      for (;;) {
        int n = service::watch_inbox_once(b);
        if (n) {
          b.drain_embed_jobs(50);
          std::cout << "imported pages~=" << n << "\n";
        }
        Sleep(2000);
      }
    }
    int n = service::watch_inbox_once(b);
    b.drain_embed_jobs(50);
    std::cout << "inbox processed, pages=" << n << "\n";
    return 0;
  });
}

int cmd_sync(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    auto path = join_positional(args, {"--brain", "--once", "--watch", "--interval", "--source"});
    if (path.empty()) {
      std::cerr << "usage: qbrain sync <notes-dir> [--watch] [--once] [--interval ms]\n";
      return 1;
    }
    auto source = opt(args, "--source", "default");
    int interval = 2000;
    try {
      if (!opt(args, "--interval").empty()) interval = std::stoi(opt(args, "--interval"));
    } catch (...) {
    }
    if (flag(args, "--watch")) {
      int cycles = flag(args, "--once") ? 1 : 0;
      int n = service::live_sync_watch(b, path, interval, cycles, source);
      b.drain_embed_jobs(100);
      std::cout << "live_sync_watch imported_pages_total=" << n << "\n";
      return 0;
    }
    auto r = service::live_sync_once(b, path, source);
    b.drain_embed_jobs(100);
    std::cout << "live_sync scanned=" << r.scanned << " imported=" << r.imported_pages
              << " skipped=" << r.skipped << " errors=" << r.errors << "\n";
    return r.errors && !r.imported_pages ? 1 : 0;
  });
}

int cmd_worker(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    int cycles = flag(args, "--once") ? 1 : 1000000;
    for (int i = 0; i < cycles; ++i) {
      int n = jobs::drain_jobs(b, 20, "cli-worker");
      int legacy = b.drain_embed_jobs(10);
      int inbox_n = service::watch_inbox_once(b);
      if (n || legacy || inbox_n)
        std::cout << "worker jobs=" << n << " legacy_embed=" << legacy << " inbox=" << inbox_n
                  << "\n";
      if (flag(args, "--once")) break;
      Sleep(3000);
    }
    return 0;
  });
}

int cmd_dream(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    cycle::DreamOpts opts;
    opts.dry_run = !flag(args, "--apply");
    opts.phase = opt(args, "--phase");
    opts.retention_hours = opt(args, "--retention-hours");
    if (flag(args, "--json")) {
      auto report = cycle::run_dream(b, opts);
      std::cout << cycle::report_to_json(report) << "\n";
      return report.status == "failed" ? 1 : 0;
    }
    auto report = cycle::run_dream(b, opts);
    std::cout << cycle::report_to_text(report);
    if (opts.dry_run) std::cout << "re-run with --apply to write\n";
    return report.status == "failed" ? 1 : 0;
  });
}

int cmd_delete(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    auto slug = join_positional(args, {"--brain", "--source", "--json"});
    if (slug.empty()) {
      std::cerr << "usage: qbrain delete <slug>\n";
      return 1;
    }
    auto source = opt(args, "--source", "default");
    if (!b.soft_delete(slug, source)) {
      std::cerr << "not found or already deleted: " << slug << "\n";
      return 1;
    }
    std::cout << "deleted " << slug << "\n";
    return 0;
  });
}

int cmd_embed(const std::vector<std::string>& args) {
  return with_brain(args, [&](Brain& b) {
    if (flag(args, "--drain")) {
      int n = b.drain_embed_jobs(1000);
      std::cout << "drained embed jobs; chunks_updated=" << n << "\n";
      return 0;
    }
    std::vector<Chunk> targets;
    if (flag(args, "--all")) {
      targets = b.list_chunks_missing_embedding(100000);
    } else {
      auto slug = opt(args, "--slug");
      if (slug.empty()) {
        std::cerr << "usage: qbrain embed --all | --slug s\n";
        return 1;
      }
      auto page = b.get_page(slug);
      if (!page) {
        std::cerr << "not found\n";
        return 1;
      }
      targets = b.get_chunks(page->id);
    }
    if (targets.empty()) {
      std::cout << "nothing to embed\n";
      return 0;
    }
    int done = 0;
    for (size_t i = 0; i < targets.size(); i += 16) {
      size_t n = (std::min)(static_cast<size_t>(16), targets.size() - i);
      std::vector<std::string> texts;
      for (size_t j = 0; j < n; ++j) texts.push_back(targets[i + j].text);
      auto er = ai::embed_texts(b.config(), texts);
      if (!er.ok) {
        std::cerr << "embed failed: " << er.error << "\n";
        return 2;
      }
      for (size_t j = 0; j < n && j < er.vectors.size(); ++j) {
        b.update_chunk_embedding(targets[i + j].id, er.vectors[j], er.model);
        ++done;
      }
    }
    std::cout << "embedded " << done << " chunks\n";
    return 0;
  });
}

}  // namespace

int run(int argc, char** argv) {
  ops::register_builtin_ops();
#ifdef _WIN32
  SetConsoleOutputCP(CP_UTF8);
  SetConsoleCP(CP_UTF8);
#endif
  std::vector<std::string> args;
  for (int i = 1; i < argc; ++i) args.emplace_back(argv[i]);
  if (args.empty() || args[0] == "help" || args[0] == "-h" || args[0] == "--help") {
    print_help();
    return 0;
  }
  if (args[0] == "version" || args[0] == "--version") {
    // N37 D2: version from the single C++ source of truth (include/qbrain/version.hpp).
    std::cout << "Qbrain " << QBRAIN_VERSION_STRING << " (windows-native c++)\n";
    return 0;
  }

  try {
    const auto& cmd = args[0];
    std::vector<std::string> rest(args.begin() + 1, args.end());
    if (cmd == "context") return cmd_context(rest);
    if (cmd == "hook" && !rest.empty() && rest[0] == "diagnostics")
      return integration::run_hook_diagnostics(std::vector<std::string>(rest.begin()+1,rest.end()));
    if (cmd == "hook") return integration::run_hook(rest);
    if (cmd == "init") return cmd_init(rest);
    if (cmd == "doctor") return cmd_doctor(rest);
    if (cmd == "config") return cmd_config(rest);
    if (cmd == "put") return cmd_put(rest);
    if (cmd == "get") return cmd_get(rest);
    if (cmd == "list") return cmd_list(rest);
    if (cmd == "capture") return cmd_capture(rest);
    if (cmd == "memory") return cmd_memory(rest);
    if (cmd == "fact") return cmd_fact(rest);
    if (cmd == "session-capture") return cmd_session_capture(rest);  // N41
    if (cmd == "import") return cmd_import(rest);
    if (cmd == "search") return cmd_search(rest);
    if (cmd == "think") return cmd_think(rest);
    if (cmd == "graph") return cmd_graph(rest);
    if (cmd == "delete") return cmd_delete(rest);
    if (cmd == "embed") return cmd_embed(rest);
    if (cmd == "serve") return cmd_serve(rest);
    if (cmd == "inbox") return cmd_inbox(rest);
    if (cmd == "sync") return cmd_sync(rest);
    if (cmd == "worker") return cmd_worker(rest);
    if (cmd == "dream") return cmd_dream(rest);
    std::cerr << "unknown command: " << cmd << "\n";
    print_help();
    return 1;
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << "\n";
    return 2;
  }
}

}  // namespace qbrain::cli
