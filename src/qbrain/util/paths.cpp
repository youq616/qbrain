#include "qbrain/util/paths.hpp"
#include <algorithm>
#include <cstdlib>
#include <stdexcept>
#include <climits>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <shlobj.h>
#pragma comment(lib, "shell32.lib")
#endif

namespace qbrain::util {

#ifdef _WIN32
std::wstring utf8_to_wide(std::string_view s) {
  if (s.empty()) return {};
  if (s.size() > static_cast<size_t>(INT_MAX)) throw std::length_error("UTF-8 input too long");
  const int length = static_cast<int>(s.size());
  const int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), length, nullptr, 0);
  if (!n) throw std::runtime_error("invalid UTF-8 input");
  std::wstring w(static_cast<size_t>(n), L'\0');
  if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), length, w.data(), n) != n)
    throw std::runtime_error("UTF-8 conversion failed");
  return w;
}
std::string wide_to_utf8(std::wstring_view w) {
  if (w.empty()) return {};
  if (w.size() > static_cast<size_t>(INT_MAX)) throw std::length_error("UTF-16 input too long");
  const int length = static_cast<int>(w.size());
  const int n = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, w.data(), length, nullptr, 0, nullptr, nullptr);
  if (!n) throw std::runtime_error("invalid UTF-16 input");
  std::string s(static_cast<size_t>(n), '\0');
  if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, w.data(), length, s.data(), n, nullptr, nullptr) != n)
    throw std::runtime_error("UTF-16 conversion failed");
  return s;
}
#endif

fs::path local_app_data() {
#ifdef _WIN32
  // Honor an explicit process override first so native tests and isolated CLI
  // runs can use their own %LOCALAPPDATA% data root.
  const DWORD needed = GetEnvironmentVariableW(L"LOCALAPPDATA", nullptr, 0);
  if (needed) {
    std::wstring value(needed, L'\0');
    const DWORD got = GetEnvironmentVariableW(L"LOCALAPPDATA", value.data(), needed);
    if (got == 0 || got >= needed) throw std::runtime_error("LOCALAPPDATA changed while reading");
    value.resize(got);
    return fs::path(value);
  }
  wchar_t* buf = nullptr;
  if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &buf)) && buf) {
    std::wstring w(buf);
    CoTaskMemFree(buf);
    return fs::path(w);
  }
  throw std::runtime_error("LOCALAPPDATA not found");
#else
  if (const char* e = std::getenv("HOME")) return fs::path(e) / ".local" / "share";
  throw std::runtime_error("HOME not found");
#endif
}

fs::path qbrain_root() { return local_app_data() / "Qbrain"; }
fs::path brains_root() { return qbrain_root() / "brains"; }

std::string normalize_brain_id(const std::string& brain_id) {
  if (brain_id.empty() || brain_id.size() > 64) throw std::runtime_error("invalid brain id");
  std::string out;
  out.reserve(brain_id.size());
  for (unsigned char c : brain_id) {
    if (c >= 'A' && c <= 'Z')
      out.push_back(static_cast<char>(c - 'A' + 'a'));
    else if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-')
      out.push_back(static_cast<char>(c));
    else
      throw std::runtime_error("invalid brain id");
  }
  static const char* kReserved[] = {"con",  "prn",  "aux",  "nul",  "com1", "com2", "com3",
                                    "com4", "com5", "com6", "com7", "com8", "com9", "lpt1",
                                    "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8",
                                    "lpt9"};
  for (auto* r : kReserved) {
    if (out == r) throw std::runtime_error("invalid brain id");
  }
  return out;
}

fs::path brain_dir(const std::string& brain_id) { return brains_root() / normalize_brain_id(brain_id); }
fs::path brain_db_path(const std::string& brain_id) {
  return brain_dir(brain_id) / "brain.db";
}
fs::path config_path() { return qbrain_root() / "config.json"; }
fs::path audit_dir() { return qbrain_root() / "audit"; }

void ensure_dir(const fs::path& p) {
  std::error_code ec;
  fs::create_directories(p, ec);
}

std::string path_to_utf8(const fs::path& p) {
#ifdef _WIN32
  return wide_to_utf8(p.wstring());
#else
  return p.string();
#endif
}

fs::path utf8_to_path(const std::string& s) {
#ifdef _WIN32
  return fs::path(utf8_to_wide(s));
#else
  return fs::path(s);
#endif
}

}  // namespace qbrain::util
