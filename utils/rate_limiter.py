"""Gap 7: Adaptive rate limiting with exponential backoff."""

import time
import logging

log = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    def __init__(self, base_delay=1.0, max_delay=30.0, cooldown=120.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.cooldown = cooldown
        self.current_delay = base_delay
        self.consecutive_errors = 0
        self.total_requests = 0
        self.total_errors = 0
        self._last_request_time = 0

    def wait(self):
        elapsed = time.time() - self._last_request_time
        remaining = self.current_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_time = time.time()
        self.total_requests += 1

    def report_success(self):
        self.consecutive_errors = 0
        self.current_delay = max(self.base_delay, self.current_delay * 0.9)

    def report_soft_error(self):
        self.consecutive_errors += 1
        self.total_errors += 1
        self.current_delay = min(self.max_delay, self.current_delay * 1.5)
        log.info("Rate limiter: soft error #%d, delay now %.1fs",
                 self.consecutive_errors, self.current_delay)

    def report_hard_error(self):
        self.consecutive_errors += 1
        self.total_errors += 1
        self.current_delay = min(self.max_delay, self.current_delay * 3.0)
        log.warning("Rate limiter: HARD error #%d, delay now %.1fs",
                    self.consecutive_errors, self.current_delay)
        if self.consecutive_errors >= 5:
            log.warning("Cooling down for %.0fs...", self.cooldown)
            time.sleep(self.cooldown)
            self.consecutive_errors = 0
            self.current_delay = self.base_delay * 2

    def should_stop(self):
        return self.consecutive_errors >= 10