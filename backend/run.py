import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", os.getenv("PORT", "5001")))
    app.run(host=host, port=port)
