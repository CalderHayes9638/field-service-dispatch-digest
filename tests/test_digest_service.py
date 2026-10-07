from datetime import date
from typing import Any

from field_digest.digest_service import DigestRequest, deliver_digest
from field_digest.infrai_client import InfraiClient


class RecordingMailer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_digest(self, **request: Any) -> dict[str, object]:
        self.calls.append(request)
        return {"message_id": "msg_field_2048"}


class SuccessfulResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def json(self) -> dict[str, object]:
        return {"ok": True, "data": {"message_id": "msg_field_2048"}}


class RecordingSession:
    def __init__(self) -> None:
        self.request_kwargs: dict[str, Any] = {}

    def request(self, **kwargs: Any) -> SuccessfulResponse:
        self.request_kwargs = kwargs
        return SuccessfulResponse()


def test_infrai_client_wraps_batch_email_in_messages() -> None:
    session = RecordingSession()
    client = InfraiClient(api_key="test-key", session=session)  # type: ignore[arg-type]

    client.send_digest(
        to=["chenhua@changba.com"],
        subject="Dispatch digest",
        html="<p>One open order</p>",
        delivery_key="digest-2026-10-06",
    )

    assert session.request_kwargs["json"] == {
        "messages": [
            {
                "to": ["chenhua@changba.com"],
                "subject": "Dispatch digest",
                "html": "<p>One open order</p>",
            }
        ]
    }


def test_digest_excludes_closed_orders_and_inactive_subscribers() -> None:
    request = DigestRequest.model_validate(
        {
            "service_area": "North River",
            "digest_date": "2026-09-14",
            "subscribers": [
                {"email": "dispatcher@example.com", "active": True},
                {"email": "former-lead@example.com", "active": False},
            ],
            "work_orders": [
                {
                    "work_order_id": "WO-2048",
                    "site_name": "Harbor Clinic",
                    "dispatch_status": "on_site",
                    "photos": [
                        {
                            "url": "https://images.example.com/wo-2048/compressor.jpg",
                            "caption": "Compressor before repair",
                        }
                    ],
                    "technician_follow_up": {
                        "technician_name": "Mina Chen",
                        "note": "Confirm pressure after the evening cycle",
                    },
                },
                {
                    "work_order_id": "WO-2047",
                    "site_name": "Market Annex",
                    "dispatch_status": "completed",
                },
            ],
        }
    )
    mailer = RecordingMailer()

    result = deliver_digest(request, mailer)

    assert result.model_dump() == {
        "sent": True,
        "recipients": 1,
        "included_work_orders": 1,
        "message_id": "msg_field_2048",
    }
    assert mailer.calls[0]["to"] == ["dispatcher@example.com"]
    assert "WO-2048" in mailer.calls[0]["html"]
    assert "Compressor before repair" in mailer.calls[0]["html"]
    assert "Confirm pressure after the evening cycle" in mailer.calls[0]["html"]
    assert "WO-2047" not in mailer.calls[0]["html"]
    assert mailer.calls[0]["delivery_key"] == "field-digest-North River-2026-09-14"


def test_empty_attention_list_skips_email() -> None:
    request = DigestRequest(
        service_area="North River",
        digest_date=date(2026, 9, 14),
        subscribers=[{"email": "dispatcher@example.com"}],
        work_orders=[],
    )
    mailer = RecordingMailer()

    result = deliver_digest(request, mailer)

    assert result.sent is False
    assert mailer.calls == []
