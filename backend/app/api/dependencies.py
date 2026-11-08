from hmac import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import get_settings


def verify_app_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings().app_api_key
    if x_api_key is None or not compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalida",
        )

