"""Launch the same dashboard routes without requiring the TechPulse Postgres stack."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from frontend.api import router

ROOT = Path(__file__).resolve().parent


def install_dashboard(app):
    app.include_router(router)
    app.mount("/dashboard-assets", StaticFiles(directory=ROOT / "static"), name="dashboard-assets")

    @app.get("/dashboard", include_in_schema=False)
    def dashboard():
        return FileResponse(ROOT / "static" / "index.html")


def create_app():
    app = FastAPI(title="AgentShield local demo")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])
    install_dashboard(app)

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(ROOT / "static" / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("frontend.server:app", host="127.0.0.1", port=8787)
