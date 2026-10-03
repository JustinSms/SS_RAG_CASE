def codes(response):
    return [p["code"] for p in response.json()["problems"]]


def test_health_reports_missing_key(make_client):
    with make_client(key_status="missing") as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["healthy"] is False
    assert codes(response) == ["api_key_missing"]


def test_health_reports_invalid_key(make_client):
    with make_client(key_status="invalid") as client:
        assert codes(client.get("/api/health")) == ["api_key_invalid"]


def test_health_ok(make_client):
    with make_client() as client:
        body = client.get("/api/health").json()
    assert body == {"healthy": True, "problems": []}


def test_health_reports_unreachable_db(make_client):
    with make_client(db_ok=False) as client:
        body = client.get("/api/health").json()
    assert body["healthy"] is False
    assert [p["code"] for p in body["problems"]] == ["db_unreachable"]


def test_low_memory_is_a_warning_not_unhealthy(make_client):
    with make_client(memory_gb=4.0) as client:
        body = client.get("/api/health").json()
    assert body["healthy"] is True
    assert [p["code"] for p in body["problems"]] == ["low_memory"]
