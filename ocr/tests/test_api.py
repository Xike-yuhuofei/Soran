from __future__ import annotations

import json
import time

import httpx
from conftest import PRICING_FIXTURE, image_bytes, make_ecommerce_image
from fastapi.testclient import TestClient

from app.main import create_app


def mock_transport(
    text: str = "# 标题\n**面料成分**：92%莫代尔 8%氨纶\n价格：¥129.00",
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.siliconflow.cn":
            return httpx.Response(200, text=PRICING_FIXTURE)
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "id": "mock-request",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": text},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600},
                },
            )
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler)


def make_client(settings) -> TestClient:
    app = create_app(settings, transport=mock_transport())
    return TestClient(app)


def upload_sample(client: TestClient, filename: str = "sample.png"):
    data = image_bytes(make_ecommerce_image(height=2000))
    response = client.post(
        "/api/sessions",
        files=[("files", (filename, data, "image/png"))],
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_full_api_flow(settings):
    with make_client(settings) as client:
        session = upload_sample(client)
        assert len(session["images"]) == 1
        image_id = session["images"][0]["image_id"]

        config = client.get("/api/config").json()
        assert config["api_key_configured"] is True
        assert "SILICONFLOW" not in json.dumps(config)

        policy = client.get("/api/policy").json()
        assert policy["models"]["deepseek-ai/DeepSeek-OCR"]["free"] is True

        response = client.post(
            "/api/ocr/jobs",
            json={
                "session_id": session["session_id"],
                "image_order": [image_id],
                "mode": "text",
                "consent_cloud_upload": True,
                "use_review": False,
                "use_cache": True,
            },
        )
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]

        progress = None
        for _ in range(50):
            progress = client.get(f"/api/ocr/jobs/{job_id}").json()
            if progress["status"] in {"completed", "partial", "failed", "blocked"}:
                break
            time.sleep(0.1)
        assert progress is not None
        assert progress["status"] in {"completed", "partial"}

        result = client.get(f"/api/ocr/jobs/{job_id}/result").json()
        assert result["status"] in {"completed", "partial"}
        assert result["text"]
        assert "**" not in result["text"]
        assert result["images"][0]["chunks"][0]["y0"] == 0
        assert result["images"][0]["chunks"][-1]["y1"] == 2000
        assert result["images"][0]["chunks"][0]["engine"] == settings.primary_model
        assert result["images"][0]["chunks"][0]["confidence"] is None
        assert "test-key-not-real" not in json.dumps(result)

        for fmt, media in [
            ("txt", "text/plain"),
            ("md", "text/markdown"),
            ("json", "application/json"),
        ]:
            export = client.get(f"/api/ocr/jobs/{job_id}/export?format={fmt}")
            assert export.status_code == 200
            assert media in export.headers["content-type"]
            assert "attachment" in export.headers["content-disposition"]
            if fmt == "json":
                payload = json.loads(export.text)
                assert payload["images"][0]["chunks"][0]["y1"] > 0
                assert "raw_text" in payload["images"][0]["chunks"][0]

        edited = client.put(
            f"/api/ocr/jobs/{job_id}/result",
            json={"documents": [{"image_id": image_id, "text": "人工修改\n品牌：SORAN"}]},
        )
        assert edited.status_code == 200
        assert edited.json()["images"][0]["edited"] is True
        assert "人工修改" in client.get(f"/api/ocr/jobs/{job_id}/export?format=txt").text

        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        assert "daily_usage" in health


def test_apply_review_text_endpoint(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.siliconflow.cn":
            return httpx.Response(200, text=PRICING_FIXTURE)
        if request.url.path.endswith("/chat/completions"):
            payload = json.loads(request.content)
            text = (
                "面料成分：92%莫代尔 8%氨纶"
                if payload.get("model") == settings.primary_model
                else "面料成分：95%莫代尔 5%氨纶"
            )
            return httpx.Response(
                200,
                json={
                    "id": "mock-review",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": text},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                },
            )
        return httpx.Response(404)

    app = create_app(settings, transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        session = upload_sample(client, filename="review.png")
        image_id = session["images"][0]["image_id"]
        response = client.post(
            "/api/ocr/jobs",
            json={
                "session_id": session["session_id"],
                "image_order": [image_id],
                "consent_cloud_upload": True,
                "use_review": True,
                "use_cache": False,
            },
        )
        job_id = response.json()["job_id"]
        for _ in range(30):
            progress = client.get(f"/api/ocr/jobs/{job_id}").json()
            if progress["status"] in {"completed", "partial", "failed", "blocked"}:
                break
            time.sleep(0.1)
        result = client.get(f"/api/ocr/jobs/{job_id}/result").json()
        chunk = result["images"][0]["chunks"][0]
        assert chunk["review_text"] == "面料成分：95%莫代尔 5%氨纶"

        applied = client.post(
            f"/api/ocr/jobs/{job_id}/chunks/apply",
            json={"image_id": image_id, "chunk_index": 0, "source": "review"},
        )
        assert applied.status_code == 200
        chunk = applied.json()["images"][0]["chunks"][0]
        assert chunk["manual_override"] is True
        assert "95%莫代尔" in applied.json()["text"]
        assert "92%莫代尔" not in applied.json()["text"]

        restored = client.post(
            f"/api/ocr/jobs/{job_id}/chunks/apply",
            json={"image_id": image_id, "chunk_index": 0, "source": "primary"},
        )
        assert restored.status_code == 200
        chunk = restored.json()["images"][0]["chunks"][0]
        assert chunk["manual_override"] is False
        assert "92%莫代尔" in restored.json()["text"]


def test_consent_required(settings):
    with make_client(settings) as client:
        session = upload_sample(client)
        response = client.post(
            "/api/ocr/jobs",
            json={
                "session_id": session["session_id"],
                "consent_cloud_upload": False,
            },
        )
        assert response.status_code == 400
        assert "确认" in response.json()["detail"]


def test_local_upload_does_not_contact_cloud(settings):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            calls["count"] += 1
        if request.url.host == "www.siliconflow.cn":
            return httpx.Response(200, text=PRICING_FIXTURE)
        return httpx.Response(404)

    app = create_app(settings, transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        session = upload_sample(client)
        assert session["images"][0]["width"] == 750
        assert calls["count"] == 0, "upload must not trigger cloud OCR"


def test_invalid_upload_rejected(settings):
    with make_client(settings) as client:
        response = client.post(
            "/api/sessions",
            files=[("files", ("fake.png", b"not an image", "image/png"))],
        )
        assert response.status_code == 400
        assert "解码失败" in response.json()["detail"]


def test_oversized_width_rejected(settings):
    settings.max_image_width = 1000
    with make_client(settings) as client:
        data = image_bytes(make_ecommerce_image(height=10, width=1200))
        response = client.post(
            "/api/sessions",
            files=[("files", ("wide.png", data, "image/png"))],
        )
        assert response.status_code == 400
        assert "宽度" in response.json()["detail"]


def test_too_many_files_rejected(settings):
    with make_client(settings) as client:
        data = image_bytes(make_ecommerce_image(height=100, width=200))
        files = [("files", (f"{i}.png", data, "image/png")) for i in range(6)]
        response = client.post("/api/sessions", files=files)
        assert response.status_code == 400
        assert "最多" in response.json()["detail"]


def test_unknown_session_and_image(settings):
    with make_client(settings) as client:
        assert client.get("/api/sessions/not-a-uuid").status_code == 404
        response = client.post(
            "/api/ocr/jobs",
            json={
                "session_id": "00000000-0000-0000-0000-000000000000",
                "consent_cloud_upload": True,
            },
        )
        assert response.status_code == 404


def test_bad_export_format(settings):
    with make_client(settings) as client:
        session = upload_sample(client)
        response = client.get(f"/api/ocr/jobs/{session['session_id']}/export?format=pdf")
        assert response.status_code == 404


def test_path_like_ids_are_rejected(settings):
    with make_client(settings) as client:
        response = client.get("/api/sessions/../etc/passwd")
        assert response.status_code == 404
        response = client.get("/api/sessions/00000000-0000-0000-0000-000000000000/images/x/preview")
        assert response.status_code == 404
