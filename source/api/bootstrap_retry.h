#pragma once

// Missing or incompatible endpoints are not transient network failures.
inline bool jf_bootstrap_fallback(int status) {
    return status == 404 || status == 405;
}
inline bool jf_bootstrap_retryable(int status) {
    return status < 0 || status == 408 || status == 425 || status == 429 ||
           (status >= 500 && status <= 599);
}
