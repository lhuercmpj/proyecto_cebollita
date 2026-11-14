import pytest
from fastapi.testclient import TestClient

from src.main import app

# 5173: pagina servida por Docker. 5174: `npm run dev` en frontend/.
ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5174"]


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_allowed_origin_gets_cors_header(origin):
    client = TestClient(app)
    response = client.options(
        "/api/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unknown_origin_is_rejected():
    client = TestClient(app)
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://sitio-ajeno.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers
