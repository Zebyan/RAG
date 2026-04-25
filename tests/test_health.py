def test_health_ok(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"ok", "degraded"}
    assert "vector_store" in data["dependencies"]
    assert "llm" in data["dependencies"]
    assert "object_store" in data["dependencies"]
