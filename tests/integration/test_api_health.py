class TestHealth:
    def test_returns_200_when_db_ok(self, app_client, mocker):
        # check_connection is already patched to a no-op in app_client fixture
        response = app_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_returns_503_when_db_down(self, app_client, mocker):
        mocker.patch(
            "Server.api.app.check_connection",
            side_effect=Exception("DB is down"),
        )
        response = app_client.get("/health")
        assert response.status_code == 503
