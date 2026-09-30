#pragma once
// N48U: SQL for the new policy of the existing optional PostgreSQL cache schema.
#include <string>

namespace qbrain::context::pg::directory_policy {
inline std::string member(const char* row) {
  const std::string r(row);
  // Both text arguments remain literal. No LIKE wildcard or locale case folding.
  // Every validated cached URI is a directory ending in '/', including namespace root.
  return "c.source_id="+r+".source_id AND pg_catalog.strpos('qbrain://' || "+r+
    ".source_id || '/' || CASE WHEN "+r+".type='session_fragment' THEN 'memories' WHEN "+r+
    ".type='skill' THEN 'skills' ELSE 'resources' END || '/' || "+r+".slug,c.uri)=1";
}
inline const std::string& body() {
  static const std::string sql =
    "\nBEGIN\n IF TG_OP = 'TRUNCATE' THEN\n"
    "  UPDATE public.context_cache SET dirty=1,l0='',l1='',refs_json='[]';\n"
    " ELSIF TG_OP = 'INSERT' THEN\n"
    "  UPDATE public.context_cache AS c SET dirty=1,l0='',l1='',refs_json='[]' WHERE "+member("NEW")+";\n"
    " ELSIF TG_OP = 'DELETE' THEN\n"
    "  UPDATE public.context_cache AS c SET dirty=1,l0='',l1='',refs_json='[]' WHERE "+member("OLD")+";\n"
    " ELSE\n"
    "  UPDATE public.context_cache AS c SET dirty=1,l0='',l1='',refs_json='[]' WHERE ("+member("OLD")+") OR ("+member("NEW")+");\n"
    " END IF;\n RETURN NULL;\nEND;\n";
  return sql;
}
} // namespace qbrain::context::pg::directory_policy
