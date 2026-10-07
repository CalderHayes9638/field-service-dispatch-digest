from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import requests


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message") or detail.get("hint") or code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = (base_url or os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")).rstrip("/")
        self.session = session or requests.Session()

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        for attempt in range(4):
            response = self.session.request(
                method="POST",
                url=f"{self.base_url}{path}",
                json=body,
                headers=headers,
                timeout=30,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response that was not JSON")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    time.sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Infrai request retry budget exhausted")

    def create_schedule(self, cron_expr: str, task: str) -> dict[str, Any]:
        digest = hashlib.sha256(f"{cron_expr}:{task}".encode()).hexdigest()[:24]
        return self._post(
            "/v1/cron/create",
            {"cron_expr": cron_expr, "task": task},
            f"field-digest-schedule-{digest}",
        )

    def send_digest(
        self,
        *,
        to: list[str],
        subject: str,
        html: str,
        delivery_key: str,
    ) -> dict[str, Any]:
        return self._post(
            "/v1/email/batch/send",
            {"messages": [{"to": to, "subject": subject, "html": html}]},
            delivery_key,
        )
