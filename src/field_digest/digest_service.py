from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from html import escape
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DispatchStatus(str, Enum):
    UNASSIGNED = "unassigned"
    DISPATCHED = "dispatched"
    ON_SITE = "on_site"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkOrderPhoto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    caption: str = Field(min_length=1, max_length=160)


class TechnicianFollowUp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technician_name: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=500)
    due_at: datetime | None = None


class WorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str = Field(min_length=1, max_length=80)
    site_name: str = Field(min_length=1, max_length=120)
    dispatch_status: DispatchStatus
    photos: list[WorkOrderPhoto] = Field(default_factory=list, max_length=8)
    technician_follow_up: TechnicianFollowUp | None = None


class Subscriber(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    active: bool = True


class DigestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_area: str = Field(min_length=1, max_length=100)
    digest_date: date
    subscribers: list[Subscriber] = Field(min_length=1, max_length=200)
    work_orders: list[WorkOrder] = Field(default_factory=list, max_length=100)


class DigestResult(BaseModel):
    sent: bool
    recipients: int
    included_work_orders: int
    message_id: str | None = None


def orders_requiring_attention(work_orders: list[WorkOrder]) -> list[WorkOrder]:
    closed = {DispatchStatus.COMPLETED, DispatchStatus.CANCELLED}
    return [order for order in work_orders if order.dispatch_status not in closed]


def render_digest(service_area: str, digest_date: date, work_orders: list[WorkOrder]) -> str:
    sections: list[str] = []
    for order in work_orders:
        photos = "".join(
            f'<li><a href="{escape(str(photo.url), quote=True)}">{escape(photo.caption)}</a></li>'
            for photo in order.photos
        )
        follow_up = order.technician_follow_up
        follow_up_html = "<p>No technician follow-up recorded.</p>"
        if follow_up:
            due = f" Due {follow_up.due_at.isoformat()}." if follow_up.due_at else ""
            follow_up_html = (
                f"<p><strong>{escape(follow_up.technician_name)}</strong>: "
                f"{escape(follow_up.note)}{escape(due)}</p>"
            )
        sections.append(
            f"<section><h2>{escape(order.work_order_id)} - {escape(order.site_name)}</h2>"
            f"<p>Dispatch: {escape(order.dispatch_status.value)}</p>"
            f"<ul>{photos}</ul>{follow_up_html}</section>"
        )
    return (
        f"<h1>{escape(service_area)} field-service digest</h1>"
        f"<p>{digest_date.isoformat()}</p>{''.join(sections)}"
    )


def deliver_digest(request: DigestRequest, mailer: Any) -> DigestResult:
    recipients = [str(item.email) for item in request.subscribers if item.active]
    included = orders_requiring_attention(request.work_orders)
    if not recipients or not included:
        return DigestResult(sent=False, recipients=len(recipients), included_work_orders=len(included))

    response = mailer.send_digest(
        to=recipients,
        subject=f"{request.service_area} dispatch digest - {request.digest_date.isoformat()}",
        html=render_digest(request.service_area, request.digest_date, included),
        delivery_key=f"field-digest-{request.service_area}-{request.digest_date.isoformat()}",
    )
    return DigestResult(
        sent=True,
        recipients=len(recipients),
        included_work_orders=len(included),
        message_id=str(response["message_id"]),
    )
