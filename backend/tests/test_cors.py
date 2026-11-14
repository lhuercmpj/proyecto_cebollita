from fastapi.testclient import TestClient

from src.main import app


def test_allowed_origin_gets_cors_header():
    client = TestClient(app)
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


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
