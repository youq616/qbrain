#pragma once
#include "qbrain/core/brain.hpp"
#include "qbrain/memory/session_memory.hpp"
namespace qbrain::context {
using Json=nlohmann::json;
Json read(Brain&,const std::string& source,const std::string& uri,const std::string& layer="L0",int budget=8192,int64_t offset=0,const std::string& revision="");
Json summary(Brain&,const std::string& source,const std::string& uri,const std::string& method="extractive",const memory::Provider& provider={});
}
