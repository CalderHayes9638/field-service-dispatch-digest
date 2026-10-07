import json
import os

from fastapi import Body, FastAPI, HTTPException
from pydantic import ValidationError

from .digest_service import DigestRequest, DigestResult, deliver_digest
from .infrai_client import InfraiClient, InfraiError


app = FastAPI(title="Field-service dispatch digest")


@app.post("/dispatch/digest", response_model=DigestResult)
def send_dispatch_digest(request: DigestRequest | None = Body(default=None)) -> DigestResult:
    try:
        digest_request = request or DigestRequest.model_validate_json(
            os.environ["DIGEST_REQUEST_JSON"]
        )
        return deliver_digest(digest_request, InfraiClient())
    except (KeyError, json.JSONDecodeError, ValidationError) as error:
        raise HTTPException(
            status_code=422,
            detail="Provide a valid request body or set DIGEST_REQUEST_JSON",
        ) from error
    except InfraiError as error:
        client_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": error.code, "message": str(error)},
        ) from error
