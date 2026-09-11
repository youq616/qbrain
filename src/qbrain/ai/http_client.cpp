#include "qbrain/ai/http_client.hpp"
#include "qbrain/version.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <utility>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winhttp.h>
#pragma comment(lib, "winhttp.lib")
#endif

namespace qbrain::ai {
namespace {
HttpResponse failure(HttpFailure kind, std::string message, int status = 0) {
  return {status, {}, std::move(message), kind};
}

bool unsafe_url_text(std::string_view s) {
  return std::any_of(s.begin(), s.end(), [](unsigned char c) {
    return c <= 0x20 || c == 0x7f || c == '\\';
  });
}

std::string validate(std::string_view base, std::string_view path,
                     std::string_view token, std::size_t body_size,
                     int timeout, std::size_t cap) {
  if (timeout < 1 || timeout > 600000) return "timeout_ms must be 1..600000";
  if (cap < 1 || cap > HTTP_MAX_RESPONSE_BYTES) return "invalid response byte limit";
  if (body_size > HTTP_MAX_REQUEST_BYTES) return "request body exceeds byte limit";
  if (base.empty() || base.size() > 8192 || unsafe_url_text(base) ||
      base.find_first_of("?#") != std::string_view::npos)
    return "invalid base_url";
  const auto scheme_end = base.find("://");
  auto scheme = std::string(base.substr(0, scheme_end));
  for (char& c : scheme) if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
  if (scheme_end == std::string_view::npos || (scheme != "http" && scheme != "https"))
    return "base_url must use HTTP or HTTPS";
  const auto authority = base.substr(scheme_end + 3,
      base.find('/', scheme_end + 3) - (scheme_end + 3));
  if (authority.empty() || authority.find('@') != std::string_view::npos)
    return "base_url must have a host and no userinfo";
  if (path.empty() || path.size() > 8192 || unsafe_url_text(path) ||
      path.find('#') != std::string_view::npos || path.starts_with("//") ||
      path.find("://") != std::string_view::npos)
    return "invalid endpoint path";
  if (token.size() > 16384 || std::any_of(token.begin(), token.end(), [](unsigned char c) {
        return c <= 0x20 || c >= 0x7f;
      })) return "invalid bearer token";
  return {};
}

#ifdef _WIN32
using Clock = std::chrono::steady_clock;

bool to_wide(std::string_view s, std::wstring& out) {
  if (s.empty()) { out.clear(); return true; }
  const int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(),
                                   static_cast<int>(s.size()), nullptr, 0);
  if (n <= 0) return false;
  out.resize(static_cast<std::size_t>(n));
  return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(),
                            static_cast<int>(s.size()), out.data(), n) == n;
}

struct InternetHandle {
  HINTERNET value = nullptr;
  explicit InternetHandle(HINTERNET h) : value(h) {}
  InternetHandle(const InternetHandle&) = delete;
  InternetHandle& operator=(const InternetHandle&) = delete;
  ~InternetHandle() { if (value) WinHttpCloseHandle(value); }
};

struct AsyncState {
  std::mutex mutex;
  std::condition_variable ready;
  DWORD completion = 0;
  DWORD error = 0;
  DWORD bytes_read = 0;
  std::array<char, 16384> buffer{};
  std::string outbound;
  std::wstring headers;
  // A separate reference belongs to the WinHTTP handle, not the caller's stack.
  // It is released only at the last callback, including cancellation paths.
  std::shared_ptr<AsyncState> handle_lifetime;
};

void CALLBACK on_status(HINTERNET, DWORD_PTR context, DWORD status, LPVOID info, DWORD size) {
  if (!context) return;
  auto* state = reinterpret_cast<AsyncState*>(context);
  if (status == WINHTTP_CALLBACK_STATUS_HANDLE_CLOSING) {
    // Microsoft documents this as the final callback for this request handle.
    auto release_after_callback = std::move(state->handle_lifetime);
    return;
  }
  if (status != WINHTTP_CALLBACK_STATUS_SENDREQUEST_COMPLETE &&
      status != WINHTTP_CALLBACK_STATUS_HEADERS_AVAILABLE &&
      status != WINHTTP_CALLBACK_STATUS_READ_COMPLETE &&
      status != WINHTTP_CALLBACK_STATUS_REQUEST_ERROR) return;
  {
    std::lock_guard lock(state->mutex);
    state->completion = status;
    if (status == WINHTTP_CALLBACK_STATUS_READ_COMPLETE) state->bytes_read = size;
    if (status == WINHTTP_CALLBACK_STATUS_REQUEST_ERROR) {
      state->error = info && size >= sizeof(WINHTTP_ASYNC_RESULT)
          ? static_cast<WINHTTP_ASYNC_RESULT*>(info)->dwError : ERROR_WINHTTP_INTERNAL_ERROR;
    }
  }
  state->ready.notify_one();
}

// Only the caller issues WinHTTP calls. Callbacks merely signal, so immediate
// completions cannot recursively start another read or deadlock a callback lock.
DWORD await(AsyncState& state, DWORD expected, Clock::time_point deadline, DWORD* count = nullptr) {
  std::unique_lock lock(state.mutex);
  if (!state.ready.wait_until(lock, deadline, [&] { return state.completion != 0; }) ||
      Clock::now() >= deadline) return ERROR_WINHTTP_TIMEOUT;
  const DWORD status = std::exchange(state.completion, 0);
  if (state.error) return state.error;
  if (status != expected) return ERROR_WINHTTP_INCORRECT_HANDLE_STATE;
  if (count) *count = state.bytes_read;
  return ERROR_SUCCESS;
}

HttpResponse network_error(DWORD code) {
  if (code == ERROR_WINHTTP_TIMEOUT)
    return failure(HttpFailure::timeout, "HTTP request deadline exceeded");
  // Numeric OS codes are useful diagnostics; URLs, headers and bodies are not.
  return failure(HttpFailure::transport, "HTTP transport failed (" + std::to_string(code) + ")");
}
#endif
}  // namespace

HttpResponse http_post_json(std::string_view base_url, std::string_view path,
                            std::string_view bearer_token, std::string_view json_body,
                            int timeout_ms, std::size_t max_response_bytes) {
#ifdef _WIN32
  const auto deadline = Clock::now() + std::chrono::milliseconds(timeout_ms > 0 ? timeout_ms : 0);
#endif
  const auto invalid = validate(base_url, path, bearer_token, json_body.size(),
                                timeout_ms, max_response_bytes);
  if (!invalid.empty()) return failure(HttpFailure::invalid_request, invalid);
#ifdef _WIN32
  std::wstring wbase, wpath, wtoken;
  if (!to_wide(base_url, wbase) || !to_wide(path, wpath) || !to_wide(bearer_token, wtoken))
    return failure(HttpFailure::invalid_request, "request URL or token is not valid UTF-8");
  URL_COMPONENTS parts{};
  parts.dwStructSize = sizeof(parts);
  parts.dwSchemeLength = parts.dwHostNameLength = parts.dwUrlPathLength =
      parts.dwUserNameLength = parts.dwPasswordLength = parts.dwExtraInfoLength = static_cast<DWORD>(-1);
  if (!WinHttpCrackUrl(wbase.c_str(), static_cast<DWORD>(wbase.size()), 0, &parts) ||
      (parts.nScheme != INTERNET_SCHEME_HTTP && parts.nScheme != INTERNET_SCHEME_HTTPS) ||
      !parts.dwHostNameLength || parts.dwUserNameLength || parts.dwPasswordLength || parts.dwExtraInfoLength)
    return failure(HttpFailure::invalid_request, "invalid base_url");
  std::wstring host(parts.lpszHostName, parts.dwHostNameLength);
  std::wstring full_path(parts.lpszUrlPath, parts.dwUrlPathLength);
  while (!full_path.empty() && full_path.back() == L'/') full_path.pop_back();
  if (wpath.front() != L'/') full_path += L'/';
  full_path += wpath;
  std::wstring agent;
  to_wide(std::string("Qbrain/") + QBRAIN_VERSION_STRING, agent);
  InternetHandle session(WinHttpOpen(agent.c_str(), WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
      WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, WINHTTP_FLAG_ASYNC));
  if (!session.value) return network_error(GetLastError());
  if (!WinHttpSetTimeouts(session.value, timeout_ms, timeout_ms, timeout_ms, timeout_ms))
    return network_error(GetLastError());
  InternetHandle connection(WinHttpConnect(session.value, host.c_str(), parts.nPort, 0));
  if (!connection.value) return network_error(GetLastError());
  const auto state = std::make_shared<AsyncState>();
  state->outbound.assign(json_body);
  state->headers = L"Content-Type: application/json\r\n";
  if (!wtoken.empty()) state->headers += L"Authorization: Bearer " + wtoken + L"\r\n";
  InternetHandle request(WinHttpOpenRequest(connection.value, L"POST", full_path.c_str(),
      nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
      parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0));
  if (!request.value) return network_error(GetLastError());
  DWORD disabled = WINHTTP_DISABLE_REDIRECTS | WINHTTP_DISABLE_COOKIES | WINHTTP_DISABLE_AUTHENTICATION;
  DWORD header_limit = 65536;
  if (!WinHttpSetOption(request.value, WINHTTP_OPTION_DISABLE_FEATURE, &disabled, sizeof(disabled)) ||
      !WinHttpSetOption(request.value, WINHTTP_OPTION_MAX_RESPONSE_HEADER_SIZE, &header_limit, sizeof(header_limit)))
    return network_error(GetLastError());
  DWORD_PTR context = reinterpret_cast<DWORD_PTR>(state.get());
  if (!WinHttpSetOption(request.value, WINHTTP_OPTION_CONTEXT_VALUE, &context, sizeof(context)))
    return network_error(GetLastError());
  if (WinHttpSetStatusCallback(request.value, on_status,
      WINHTTP_CALLBACK_FLAG_ALL_COMPLETIONS | WINHTTP_CALLBACK_FLAG_HANDLES, 0) == WINHTTP_INVALID_STATUS_CALLBACK)
    return network_error(GetLastError());
  state->handle_lifetime = state;
  if (Clock::now() >= deadline) return network_error(ERROR_WINHTTP_TIMEOUT);
  if (!WinHttpSendRequest(request.value, state->headers.c_str(), static_cast<DWORD>(state->headers.size()),
      state->outbound.empty() ? WINHTTP_NO_REQUEST_DATA : state->outbound.data(),
      static_cast<DWORD>(state->outbound.size()), static_cast<DWORD>(state->outbound.size()), context))
    return network_error(GetLastError());
  DWORD code = await(*state, WINHTTP_CALLBACK_STATUS_SENDREQUEST_COMPLETE, deadline);
  if (code) return network_error(code);
  if (!WinHttpReceiveResponse(request.value, nullptr)) return network_error(GetLastError());
  code = await(*state, WINHTTP_CALLBACK_STATUS_HEADERS_AVAILABLE, deadline);
  if (code) return network_error(code);
  DWORD status = 0, size = sizeof(status);
  if (!WinHttpQueryHeaders(request.value, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
      WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX))
    return network_error(GetLastError());
  if (status < 200 || status >= 300)
    return failure(HttpFailure::http_status, "HTTP " + std::to_string(status), static_cast<int>(status));

  // Do not trust Content-Length for allocation. A fixed stack-sized header buffer
  // plus a bounded numeric parse also rejects overflowing or malformed lengths.
  wchar_t length_text[32]{};
  size = sizeof(length_text);
  std::size_t declared = 0;
  const bool has_length = WinHttpQueryHeaders(request.value, WINHTTP_QUERY_CONTENT_LENGTH,
      WINHTTP_HEADER_NAME_BY_INDEX, length_text, &size, WINHTTP_NO_HEADER_INDEX) != FALSE;
  if (has_length) {
    bool any = false;
    for (wchar_t c : length_text) {
      if (!c) break;
      if (c < L'0' || c > L'9') return failure(HttpFailure::transport, "invalid response length");
      any = true;
      declared = declared * 10 + static_cast<std::size_t>(c - L'0');
      if (declared > max_response_bytes)
        return failure(HttpFailure::response_too_large, "response exceeds byte limit");
    }
    if (!any) return failure(HttpFailure::transport, "invalid response length");
  } else {
    code = GetLastError();
    if (code != ERROR_WINHTTP_HEADER_NOT_FOUND) return network_error(code);
  }

  std::string body;
  for (;;) {
    if (Clock::now() >= deadline) return network_error(ERROR_WINHTTP_TIMEOUT);
    // Reading one byte past the remaining allowance distinguishes exact-cap EOF
    // from an oversized chunked/unknown-length body, without growing the buffer.
    const DWORD wanted = static_cast<DWORD>(std::min(state->buffer.size(), max_response_bytes - body.size() + 1));
    if (!WinHttpReadData(request.value, state->buffer.data(), wanted, nullptr))
      return network_error(GetLastError());
    DWORD count = 0;
    code = await(*state, WINHTTP_CALLBACK_STATUS_READ_COMPLETE, deadline, &count);
    if (code) return network_error(code);
    if (count > wanted || count > max_response_bytes - body.size())
      return failure(HttpFailure::response_too_large, "response exceeds byte limit");
    if (!count) break;
    body.append(state->buffer.data(), count);
  }
  if (has_length && body.size() != declared)
    return failure(HttpFailure::transport, "incomplete response body");
  return {static_cast<int>(status), std::move(body), {}, HttpFailure::none};
#else
  return failure(HttpFailure::unsupported_platform, "HTTP client only implemented on Windows");
#endif
}
}  // namespace qbrain::ai
