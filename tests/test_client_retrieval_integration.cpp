// Combined source-scoped directory/context/observation checks; synthetic only.
#include "qbrain/accounting/logical_observation.hpp"
#include "qbrain/context/context.hpp"
#include "qbrain/integration/detail/cursor_hook.hpp"
#include "qbrain/search/directory.hpp"
#include <iostream>
#include <stdexcept>
using namespace qbrain;
using J=nlohmann::json;
namespace {
J checks=J::array();
void need(bool ok,const char* label){checks.push_back({{"name",label},{"passed",ok}});if(!ok)throw std::runtime_error(label);}
void run(){
  Brain b;b.open_at(":memory:");b.ensure_source("alpha");b.ensure_source("beta");
  b.save_config_value("embed.auto","false",false);
  for(const auto& source:{"alpha","beta"}){
    PageInput p;p.source_id=source;p.slug="docs/a";p.title="SYNTHETIC_N49C_NEEDLE";p.body="SYNTHETIC_N49C_BODY";b.put_page(p);
  }
  auto collector=std::make_shared<accounting::logical::Collector>();
  accounting::logical::Session session(collector);
  search::DirectorySearchOpts options;options.config=&b.config();options.mode="conservative";
  const auto scope=search::parse_directory_scope(b,"qbrain://alpha/resources/docs/");
  auto hits=search::directory_search(b,"SYNTHETIC_N49C_NEEDLE",nullptr,scope,options);
  need(hits.size()==1 && hits[0].source_id=="alpha","directory scope uses combined Brain without foreign source");
  b.soft_delete("docs/a","alpha");
  need(search::directory_search(b,"SYNTHETIC_N49C_NEEDLE",nullptr,scope,options).empty(),"combined directory sees deletion immediately");
  b.restore_page("docs/a","alpha");
  need(search::directory_search(b,"SYNTHETIC_N49C_NEEDLE",nullptr,scope,options).size()==1,"combined directory sees restoration");
  bool rejected=false;try{search::parse_directory_scope(b,"qbrain://alpha/resources/docs");}catch(const std::invalid_argument&){rejected=true;}
  need(rejected,"invalid directory still rejected");
  auto http=session.http_collector();session.detach();
  auto logical=collector->report(true,0);auto transport=http->report(true,0);
  need(logical["records"].empty(),"text-only scoped retrieval creates no model entries");
  need(transport["records"].empty(),"text-only scoped retrieval creates no HTTP entries");
  need(logical["total_estimate"].is_null(),"unobserved cost remains unknown");
  auto wire=integration::detail::cursor::output({{"hookSpecificOutput",{{"hookEventName","SessionStart"},{"additionalContext","SYNTHETIC_N49C_CONTEXT"}}}});
  need(wire==J{{"additional_context","SYNTHETIC_N49C_CONTEXT"}},"accepted Cursor envelope coexists with combined retrieval");
  need(integration::detail::cursor::noop({{"hook_event_name","beforeSubmitPrompt"}})==J{{"continue",true}},"Cursor prompt remains fail open without invented context");
}
}
int main(){try{run();std::cout<<J{{"passed",true},{"checks",checks},{"check_count",checks.size()}}.dump()<<'\n';return 0;}
catch(const std::exception& e){std::cout<<J{{"passed",false},{"error",e.what()},{"checks",checks}}.dump()<<'\n';return 1;}}
