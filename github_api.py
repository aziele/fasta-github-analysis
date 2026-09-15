"""Small GitHub REST client with pacing, retries, and rate-limit handling."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests


class GitHubClient:
    """GitHub REST client with pacing, retries, and rate-limit handling."""

    def __init__(
        self,
        min_sleep: float = 2.0,
        max_attempts: int = 5,
        buffer: float = 2.0,
    ):
        self.min_sleep = min_sleep
        self.max_attempts = max_attempts
        self.buffer = buffer

        self.last_request_time = 0.0
        self.total_requests = 0

        self.session = requests.Session()

    def _pace(self) -> None:
        elapsed = (
            time.monotonic()
            - self.last_request_time
        )

        sleep_time = max(
            0.0,
            self.min_sleep - elapsed,
        )

        if sleep_time > 0:
            time.sleep(
                sleep_time
                + random.uniform(0, 0.5)
            )

    @staticmethod
    def _parse_rate_limit(
        headers,
    ) -> tuple[int, int]:
        try:
            remaining = int(
                headers.get(
                    "X-RateLimit-Remaining",
                    -1,
                )
            )
        except (TypeError, ValueError):
            remaining = -1

        try:
            reset_ts = int(
                headers.get(
                    "X-RateLimit-Reset",
                    time.time(),
                )
            )
        except (TypeError, ValueError):
            reset_ts = int(
                time.time()
            )

        reset_in = max(
            0,
            int(
                reset_ts
                - time.time()
            ),
        )

        return remaining, reset_in

    def _rate_limit_wait(
        self,
        response: requests.Response,
    ) -> float:
        retry_after = response.headers.get(
            "Retry-After"
        )

        if retry_after is not None:
            try:
                return (
                    float(retry_after)
                    + self.buffer
                )
            except ValueError:
                pass

        _, reset_in = (
            self._parse_rate_limit(
                response.headers
            )
        )

        return (
            max(reset_in, 5)
            + self.buffer
        )

    def get(
        self,
        url: str,
        headers: dict[str, str],
        params: dict | None = None,
    ) -> tuple[int | None, Any]:
        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            try:
                self._pace()

                self.total_requests += 1

                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30,
                )

                self.last_request_time = (
                    time.monotonic()
                )

                status = (
                    response.status_code
                )

                try:
                    data = response.json()
                except ValueError:
                    data = None

                if status == 200:
                    remaining, reset_in = (
                        self._parse_rate_limit(
                            response.headers
                        )
                    )

                    logging.info(
                        "Request succeeded "
                        "(remaining=%s, reset_in=%ss)",
                        remaining,
                        reset_in,
                    )

                    if (
                        remaining != -1
                        and remaining <= 1
                    ):
                        time.sleep(
                            max(reset_in, 1)
                            + self.buffer
                        )

                    return status, data

                if status in {
                    403,
                    429,
                }:
                    wait = (
                        self._rate_limit_wait(
                            response
                        )
                    )

                    logging.warning(
                        "Rate-limit response "
                        "status=%s; retry %s/%s "
                        "in %.1fs",
                        status,
                        attempt,
                        self.max_attempts,
                        wait,
                    )

                    if attempt < self.max_attempts:
                        time.sleep(wait)

                    continue

                if status in {
                    404,
                    422,
                }:
                    return status, data

                wait = min(
                    60,
                    2**attempt
                    + random.uniform(0, 2),
                )

                logging.warning(
                    "Request failed status=%s; "
                    "retry %s/%s in %.1fs",
                    status,
                    attempt,
                    self.max_attempts,
                    wait,
                )

                if attempt < self.max_attempts:
                    time.sleep(wait)

            except requests.RequestException as exc:
                wait = min(
                    60,
                    2**attempt,
                )

                logging.warning(
                    "Request exception %r; "
                    "retry %s/%s in %.1fs",
                    exc,
                    attempt,
                    self.max_attempts,
                    wait,
                )

                if attempt < self.max_attempts:
                    time.sleep(wait)

        logging.error(
            "Request failed after %s attempts: "
            "%s params=%s",
            self.max_attempts,
            url,
            params,
        )

        return None, None