#pragma once
// Pure, bounded OpenCode JSONC editing. No file/brain/network side effects.
#include "qbrain/util/strict_json.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <algorithm>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

namespace qbrain::integration::opencode {
using Json = nlohmann::json;
inline constexpr std::size_t config_limit = 65536;
struct Error : std::runtime_error { using std::runtime_error::runtime_error; };
inline void need(bool ok, const char* why) { if (!ok) throw Error(why); }
inline void exact(const Json& j, std::initializer_list<const char*> keys) {
  need(j.is_object() && j.size()==keys.size(), "opencode_fields");
  for (auto k:keys) need(j.contains(k), "opencode_fields");
}
inline Json strict(std::string_view raw, std::size_t limit=262144) {
  try { return util::parse_unique_json(raw,limit,48); }
  catch (...) { throw Error("opencode_invalid_json"); }
}
inline bool hex_id(const std::string& s, std::size_t size=64) {
  return s.size()==size && std::all_of(s.begin(),s.end(),[](unsigned char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
inline bool whitespace(char c) { return c==' '||c=='\r'||c=='\n'||c=='\t'; }

// Keep the same byte offsets as the input. Comments/trailing commas become spaces
// only in the parser copy. The caller's exact original UTF-8 text is never rebuilt.
inline std::string jsonc_lexical(const std::string& text) {
  need(!text.empty() && text.size()<=config_limit && text.find('\0')==std::string::npos,"opencode_config_bound");
  // Validate *all* original bytes, including comment contents, as UTF-8.
  try { (void)Json(text).dump(); } catch (...) { throw Error("opencode_invalid_utf8"); }
  std::string clean=text; std::size_t i=0;
  if (text.compare(0,3,"\xEF\xBB\xBF")==0) { clean.replace(0,3,3,' '); i=3; }
  bool quoted=false, escaped=false;
  while(i<text.size()) {
    const auto c=text[i];
    if(quoted) { if(escaped) escaped=false; else if(c=='\\') escaped=true; else if(c=='"') quoted=false; ++i; continue; }
    if(c=='"') {quoted=true;++i;continue;}
    if(c=='/' && i+1<text.size() && text[i+1]=='/') {
      clean[i++]= ' ';clean[i++]= ' ';
      while(i<text.size() && text[i]!='\r' && text[i]!='\n') clean[i++]=' ';
    } else if(c=='/' && i+1<text.size() && text[i+1]=='*') {
      clean[i++]=' ';clean[i++]=' ';bool ended=false;
      while(i<text.size()) {
        if(i+1<text.size() && text[i]=='*' && text[i+1]=='/') {clean[i++]=' ';clean[i++]=' ';ended=true;break;}
        if(text[i]!='\n' && text[i]!='\r') clean[i]=' ';++i;
      }
      need(ended,"opencode_unclosed_comment");
    } else ++i;
  }
  return clean;
}
inline std::string jsonc_strict_copy(const std::string& clean) {
  std::string out=clean;bool quoted=false,escaped=false;char previous=0;
  for(std::size_t i=0;i<clean.size();++i) {
    char c=clean[i];
    if(quoted) { if(escaped) escaped=false; else if(c=='\\') escaped=true; else if(c=='"') quoted=false; continue; }
    if(c=='"') {quoted=true;previous='"';continue;}
    if(c==',') {
      auto j=i+1;while(j<clean.size() && whitespace(clean[j]))++j;
      // [,], {,} and {"a":,} are not JSONC. Do not remove a comma lacking a value.
      if(j<clean.size() && (clean[j]==']'||clean[j]=='}') && previous!='[' && previous!='{' && previous!=',' && previous!=':' && previous!=0) out[i]=' ';
    }
    if(!whitespace(c)) previous=c;
  }
  return out;
}
// All ranges are offsets into the original byte string, never decoded characters.
struct Span {
  std::size_t begin=0,end=0,finish=0,key_begin=std::string::npos;
  std::size_t comma_before=std::string::npos,comma_after=std::string::npos;
  bool object=false;
  std::map<std::string,Span> members;
};
class Document {
  std::string clean_;std::size_t at_=0;
  void ws() {while(at_<clean_.size() && whitespace(clean_[at_]))++at_;}
  std::string quoted() {
    need(at_<clean_.size()&&clean_[at_]=='"',"opencode_invalid_jsonc");
    const auto begin=at_++;bool escape=false,closed=false;
    while(at_<clean_.size()) {const char c=clean_[at_++];if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"'){closed=true;break;}}
    need(closed,"opencode_invalid_jsonc");
    return Json::parse(clean_.substr(begin,at_-begin)).get<std::string>();
  }
  Span value(unsigned depth=0) {
    need(depth<=32,"opencode_config_depth");ws();need(at_<clean_.size(),"opencode_invalid_jsonc");
    Span result;result.begin=at_;const char c=clean_[at_];
    if(c=='{'||c=='[') {
      const bool object=c=='{';const char close=object?'}':']';result.object=object;++at_;ws();
      std::size_t prior_comma=std::string::npos;
      while(at_<clean_.size()&&clean_[at_]!=close) {
        std::string key;const auto key_begin=at_;
        if(object) {key=quoted();ws();need(at_<clean_.size()&&clean_[at_]==':',"opencode_invalid_jsonc");++at_;}
        auto child=value(depth+1);child.key_begin=key_begin;child.comma_before=prior_comma;
        ws();need(at_<clean_.size(),"opencode_invalid_jsonc");
        const bool comma=clean_[at_]==',';
        if(comma){child.comma_after=at_;prior_comma=at_++;ws();}
        if(object)need(result.members.emplace(std::move(key),std::move(child)).second,"opencode_invalid_jsonc");
        if(!comma)break;
      }
      need(at_<clean_.size()&&clean_[at_]==close,"opencode_invalid_jsonc");
      result.end=at_++;result.finish=at_;return result;
    }
    if(c=='"')quoted();
    else while(at_<clean_.size()&&!whitespace(clean_[at_])&&clean_[at_]!=','&&clean_[at_]!=']'&&clean_[at_]!='}')++at_;
    result.end=at_;result.finish=at_;return result;
  }
 public:
  std::string original,lexical;Json parsed;Span root;
  explicit Document(std::string text):original(std::move(text)) {
    lexical=jsonc_lexical(original);
    parsed=strict(jsonc_strict_copy(lexical),config_limit);need(parsed.is_object(),"opencode_config_object");
    // Parse spans over the comment-free copy WITH commas, after strict validation.
    // Blanking a trailing comma would hide its exact removal location.
    clean_=lexical;root=value();ws();need(at_==clean_.size(),"opencode_invalid_jsonc");
  }
  std::string insert(const Span& object,const std::string& key,const Json& val) const {
    need(object.object&&!object.members.count(key),"opencode_name_conflict");
    auto last=object.end;while(last>0&&whitespace(lexical[last-1]))--last;
    const bool comma=last>0&&lexical[last-1]==',';
    const std::string added=(object.members.empty()||comma?"":",")+std::string("\n  ")+Json(key).dump()+": "+val.dump()+"\n";
    std::string result=original;result.insert(object.end,added);
    need(result.size()<=config_limit,"opencode_config_bound");Document check(result);return result;
  }
  std::string erase_member(const Span& object,const std::string& key) const {
    need(object.object&&object.members.count(key),"opencode_managed_entry_missing");
    const auto& member=object.members.at(key);
    need(member.key_begin<member.finish&&member.finish<=original.size(),"opencode_invalid_span");
    std::vector<std::pair<std::size_t,std::size_t>> remove={{member.key_begin,member.finish-member.key_begin}};
    const auto comma=member.comma_after!=std::string::npos?member.comma_after:member.comma_before;
    if(comma!=std::string::npos){need(comma<original.size()&&original[comma]==',',"opencode_invalid_span");remove.push_back({comma,1});}
    std::sort(remove.rbegin(),remove.rend());std::string result=original;
    for(const auto& range:remove)result.erase(range.first,range.second);
    Document check(result);return result;
  }
};
struct Settings { int major=0;std::string binary,brain,name,project;bool allow_write=false; };
inline Json server_definition(const Settings& s) {
  need(s.major==1||s.major==2,"opencode_format_required");
  need(s.name.rfind("qbrain_",0)==0 && hex_id(s.name.substr(7),24),"opencode_server_name");
  need(util::normalize_brain_id(s.brain)==s.brain,"opencode_brain_id");
  need(!s.binary.empty() && s.binary.size()<=2048 && !s.project.empty() && s.project.size()<=2048,"opencode_path_bound");
  for(const auto* path:{&s.binary,&s.project})
    need(path->find_first_of("\r\n\t{}\0",0,6)==std::string::npos,"opencode_path_interpolation");
  Json argv=Json::array({s.binary,"serve","--brain",s.brain,"--tool-profile","memory"});
  if(s.allow_write)argv.push_back("--allow-write");
  Json result={{"type","local"},{"command",argv},{"cwd",s.project},
               {"environment",{{"QBRAIN_MCP_ALLOW_WRITE","0"}}}};
  // V1 is milliseconds; V2 uses per-stage overrides, not a scalar.
  result["timeout"]=s.major==1?Json(10000):Json{{"startup",10000},{"catalog",10000}};
  result[s.major==1?"enabled":"disabled"]=s.major==1;
  return result;
}
inline std::string insert_server(const std::string& original,const Settings& s) {
  Document doc(original);auto definition=server_definition(s);auto m=doc.root.members.find("mcp");
  if(m==doc.root.members.end()) {
    Json entry={{s.name,definition}};
    return doc.insert(doc.root,"mcp",s.major==1?entry:Json{{"servers",entry}});
  }
  need(m->second.object,"opencode_mcp_object");
  if(s.major==1) {
    need(!m->second.members.count("servers"),"opencode_format_conflict");
    return doc.insert(m->second,s.name,definition);
  }
  for(const auto& el:doc.parsed["mcp"].items())
    if(el.key()!="servers" && el.value().is_object())
      need(!el.value().contains("type"),"opencode_format_conflict");
  auto servers=m->second.members.find("servers");
  if(servers==m->second.members.end())return doc.insert(m->second,"servers",Json{{s.name,definition}});
  need(servers->second.object,"opencode_servers_object");
  return doc.insert(servers->second,s.name,definition);
}
// Strip exactly the managed member and one required separator, retaining every
// other byte (including surrounding comments and empty container objects).
inline std::string strip_server(const std::string& original,const Settings& settings) {
  Document doc(original);const auto expected=server_definition(settings);
  auto m=doc.root.members.find("mcp");need(m!=doc.root.members.end()&&m->second.object,"opencode_mcp_object");
  const Span* container=&m->second;Json* semantic=&doc.parsed["mcp"];
  if(settings.major==1)need(!container->members.count("servers"),"opencode_format_conflict");
  else {
    for(const auto& item:semantic->items())if(item.key()!="servers"&&item.value().is_object())
      need(!item.value().contains("type"),"opencode_format_conflict");
    auto it=container->members.find("servers");
    need(it!=container->members.end()&&it->second.object,"opencode_servers_object");
    container=&it->second;semantic=&(*semantic)["servers"];
  }
  need(semantic->contains(settings.name),"opencode_managed_entry_missing");
  // Canonical dump also distinguishes integral parameters from floating-point
  // values; only formatting and key order may differ, not typed command settings.
  need((*semantic)[settings.name].dump()==expected.dump(),"opencode_managed_entry_changed");
  const auto stripped=doc.erase_member(*container,settings.name);semantic->erase(settings.name);
  need(Document(stripped).parsed==doc.parsed,"opencode_preservation_error");return stripped;
}
} // namespace qbrain::integration::opencode
