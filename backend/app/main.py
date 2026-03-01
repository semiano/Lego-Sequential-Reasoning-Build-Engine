from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.models import router as workspaces_router
from app.api.parts import router as parts_router
from app.api.renders import router as renders_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.storage import ensure_data_dirs

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces_router)
app.include_router(renders_router)
app.include_router(parts_router)


@app.on_event("startup")
def on_startup() -> None:
    ensure_data_dirs()
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
