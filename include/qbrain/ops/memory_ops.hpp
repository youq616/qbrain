#pragma once
#include "qbrain/ops/registry.hpp"
#include <optional>
namespace qbrain::ops {
using SourceResolver = std::function<std::optional<std::string>(OpContext&, bool, OpResult&)>;
void register_memory_ops(const SourceResolver&);
}
