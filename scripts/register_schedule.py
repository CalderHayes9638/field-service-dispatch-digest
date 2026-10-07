import os

from field_digest.infrai_client import InfraiClient


def main() -> None:
    public_url = os.environ["PUBLIC_URL"].rstrip("/")
    result = InfraiClient().create_schedule(
        cron_expr="0 17 * * 1-5",
        task=f"{public_url}/dispatch/digest",
    )
    print(f"Scheduled weekday digest: {result['job_id']}")


if __name__ == "__main__":
    main()

