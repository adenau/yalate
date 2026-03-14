from app import create_app


def test_hello_world_endpoint():
    app = create_app("testing")
    client = app.test_client()

    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.get_json() == {"message": "Hello from YaLate backend!"}
