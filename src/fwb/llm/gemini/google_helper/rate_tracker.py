# rate_tracker.py
import logging  # Import standard logging
import time
from collections import defaultdict, deque


class ModelRateTracker:
    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.ModelRateTracker")
        self.request_timestamps = defaultdict(lambda: {"rpm": deque(), "rpd": deque()})
        self.model_configs = {}

    def set_model_configs(self, configs: dict):
        self.model_configs = configs

    def record_request(self, model_name: str):
        now = time.monotonic()
        self.request_timestamps[model_name]["rpm"].append(now)
        self.request_timestamps[model_name]["rpd"].append(now)
        self._logger.debug(f"Request recorded for {model_name} at {now}")

    def _prune_timestamps(self, model_name: str, current_time: float):
        rpm_queue = self.request_timestamps[model_name]["rpm"]
        while rpm_queue and rpm_queue[0] <= current_time - 60:
            rpm_queue.popleft()

        rpd_queue = self.request_timestamps[model_name]["rpd"]
        while rpd_queue and rpd_queue[0] <= current_time - (24 * 60 * 60):
            rpd_queue.popleft()

    def is_rate_limited(self, model_name: str) -> tuple[bool, str]:
        now = time.monotonic()
        self._prune_timestamps(model_name, now)

        config = self.model_configs.get(model_name, self.model_configs.get("default"))
        if not config:
            self._logger.warning(
                f"No rate limit configuration for {model_name}. Using failsafe (10 RPM, 100 RPD)."
            )
            config = {"rpm": 10, "rpd": 100}

        rpm_limit = config.get("rpm", 0)
        rpd_limit = config.get("rpd", 0)

        rpm_queue_len = len(self.request_timestamps[model_name]["rpm"])
        if rpm_limit > 0 and rpm_queue_len >= rpm_limit:
            self._logger.info(
                f"Model {model_name} RPM limit ({rpm_limit}) met. Count in last 60s: {rpm_queue_len}"
            )
            return True, "RPM"

        rpd_queue_len = len(self.request_timestamps[model_name]["rpd"])
        if rpd_limit > 0 and rpd_queue_len >= rpd_limit:
            self._logger.info(
                f"Model {model_name} RPD limit ({rpd_limit}) met. Count in last 24h: {rpd_queue_len}"
            )
            return True, "RPD"

        return False, ""

    def get_wait_time(self, model_name: str) -> float:
        now = time.monotonic()
        self._prune_timestamps(model_name, now)

        config = self.model_configs.get(model_name, self.model_configs.get("default"))
        if not config:
            config = {"rpm": 10, "rpd": 100}

        is_limited, reason = self.is_rate_limited(model_name)

        if not is_limited:
            return 0.0

        wait_time = 0.0
        if reason == "RPM":
            rpm_limit = config.get("rpm", 0)
            rpm_queue = self.request_timestamps[model_name]["rpm"]
            if rpm_limit > 0 and len(rpm_queue) >= rpm_limit:
                timestamp_to_clear = rpm_queue[len(rpm_queue) - rpm_limit]
                wait_time = max(0.0, (timestamp_to_clear + 60.1) - now)

        elif reason == "RPD":
            rpd_limit = config.get("rpd", 0)
            rpd_queue = self.request_timestamps[model_name]["rpd"]
            if rpd_limit > 0 and len(rpd_queue) >= rpd_limit:
                timestamp_to_clear = rpd_queue[len(rpd_queue) - rpd_limit]
                wait_time = max(0.0, (timestamp_to_clear + (24 * 60 * 60) + 0.1) - now)

        self._logger.debug(
            f"Calculated wait time for {model_name} ({reason}): {wait_time:.2f}s"
        )
        return wait_time
