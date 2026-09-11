#pragma once
#include <cstddef>
#include <string>
#include <string_view>

namespace qbrain::ai {

enum class HttpFailure {
  none, invalid_request, transport, timeout, response_too_large, http_status,
  unsupported_platform
};

struct HttpResponse {
  int status = 0;
  std::string body;
  std::string error;
  HttpFailure failure = HttpFailure::none;
};

inline constexpr std::size_t HTTP_DEFAULT_RESPONSE_BYTES = 8 * 1024 * 1024;
inline constexpr std::size_t HTTP_MAX_RESPONSE_BYTES = 64 * 1024 * 1024;
inline constexpr std::size_t HTTP_MAX_REQUEST_BYTES = 32 * 1024 * 1024;

// One monotonic deadline covers all network waits (not a hard-real-time OS bound).
// Failed/incomplete responses never return a partial body or a successful status.
// Redirects, automatic authentication and cookies are disabled. No error-body echo.
HttpResponse http_post_json(std::string_view base_url, std::string_view path,
                            std::string_view bearer_token, std::string_view json_body,
                            int timeout_ms = 60000,
                            std::size_t max_response_bytes = HTTP_DEFAULT_RESPONSE_BYTES);

}  // namespace qbrain::ai
