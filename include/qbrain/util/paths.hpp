#pragma once
#include <filesystem>
#include <string>
#include <string_view>

namespace qbrain::util {

namespace fs = std::filesystem;

fs::path local_app_data();
fs::path qbrain_root();
fs::path brains_root();
std::string normalize_brain_id(const std::string& brain_id);
fs::path brain_dir(const std::string& brain_id);
fs::path brain_db_path(const std::string& brain_id);
fs::path config_path();
fs::path audit_dir();

void ensure_dir(const fs::path& p);

#ifdef _WIN32
std::wstring utf8_to_wide(std::string_view s);
std::string wide_to_utf8(std::wstring_view w);
#endif
std::string path_to_utf8(const fs::path& p);
fs::path utf8_to_path(const std::string& s);

}  // namespace qbrain::util
