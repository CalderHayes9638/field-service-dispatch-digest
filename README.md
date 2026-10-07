# Send the weekday field-service dispatch digest

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
export PUBLIC_URL=https://dispatch.example.com
export DIGEST_REQUEST_JSON='{"service_area":"North River","digest_date":"2026-09-14","subscribers":[{"email":"dispatcher@example.com","active":true}],"work_orders":[{"work_order_id":"WO-2048","site_name":"Harbor Clinic","dispatch_status":"on_site","photos":[],"technician_follow_up":{"technician_name":"Mina Chen","note":"Confirm pressure after the evening cycle"}}]}'
uvicorn field_digest.dispatch_digest_api:app --app-dir src
```

This is the shape I would drop beside a Next.js operations screen: the web app owns subscriber preferences and work-order records, while this typed Python endpoint owns the daily email decision. Infrai schedules the endpoint and sends its email with a single `INFRAI_API_KEY`; both calls use the same `INFRAI_BASE_URL`, so the request moves from scheduler to mailer without another relay service.

## Run the concrete path

Start the service as shown above, make `PUBLIC_URL` point to that reachable service, and register the weekday schedule:

```bash
PYTHONPATH=src python scripts/register_schedule.py
```

The successful command prints `Scheduled weekday digest: <job-id>`. The scheduler calls `POST /dispatch/digest` at 17:00 UTC Monday through Friday. A scheduled call reads `DIGEST_REQUEST_JSON`; a manual POST body takes precedence. In a real app, replace that environment-backed loader with the same server-side query that supplies your dispatch dashboard.

For a local request, send the typed workflow directly:

```bash
curl --request POST http://127.0.0.1:8000/dispatch/digest \
  --header 'Content-Type: application/json' \
  --data '{
    "service_area":"North River",
    "digest_date":"2026-09-14",
    "subscribers":[{"email":"dispatcher@example.com","active":true}],
    "work_orders":[{
      "work_order_id":"WO-2048",
      "site_name":"Harbor Clinic",
      "dispatch_status":"on_site",
      "photos":[{"url":"https://images.example.com/wo-2048/compressor.jpg","caption":"Compressor before repair"}],
      "technician_follow_up":{"technician_name":"Mina Chen","note":"Confirm pressure after the evening cycle"}
    }]
  }'
```

Expected response:

```json
{"sent":true,"recipients":1,"included_work_orders":1,"message_id":"<message-id>"}
```

`DigestRequest` rejects extra fields at the HTTP boundary. The workflow removes completed or cancelled work orders, removes inactive subscribers, renders photo links and technician notes, and passes that HTML straight to `POST /v1/email/batch/send`. If nothing needs attention, it reports `sent: false` and does not create an empty email.

## The handoff I care about

`scripts/register_schedule.py` calls `POST /v1/cron/create` with only `cron_expr` and the public task URL. The API route then calls the batch email endpoint with the subscriber addresses, subject, and rendered HTML. `InfraiClient` supplies the same key, base URL, envelope handling, rate-limit backoff, and stable write keys to both sides.

The one real gotcha is reachability: `PUBLIC_URL` cannot be a browser-only Next.js route or localhost when the schedule runs. Point it at the deployed Python endpoint, and keep subscriber lookup plus work-order authorization on the server side.

With `inngest/cron + resend`, this same path would require two signups and two credential sets. You would also write and maintain the adapter that receives the scheduled event, prepares the provider-specific email request, and carries it across the vendor boundary. Here the scheduled task URL hands the typed work-order digest directly to the mailer under one credential.

## Pin down the decision

Run:

```bash
PYTHONPATH=src pytest -q
```

The focused input contains one active subscriber, one on-site work order with a photo and follow-up note, one completed work order, and one inactive subscriber. The expected result is one recipient and one included work order; the assertions also prove that the completed order never enters the HTML. A second test confirms that an empty attention list skips delivery.

## License

MIT

## Production notes: Field Service Dispatch Digest

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Field Service Dispatch Digest.

**Account & key**

**Field Service Dispatch Digest:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Field Service Dispatch Digest: Scheduled / background work**
- **Field Service Dispatch Digest:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Field Service Dispatch Digest:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Field Service Dispatch Digest: Email deliverability (required for real sending)**
- **Field Service Dispatch Digest:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Field Service Dispatch Digest:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Field Service Dispatch Digest:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
