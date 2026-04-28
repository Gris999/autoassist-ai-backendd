from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import api_router
from app.core.config.settings import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "https://autoassist-ai-webb.vercel.app",
        "https://autoassist-ai-webb-27x0lj606-pedroalaca83-9867s-projects.vercel.app",
        "https://autoassist-ai-webb-rlfgvcp5m-pedroalaca83-9867s-projects.vercel.app",
    ],
    allow_origin_regex=r"^https://.*\.vercel\.app$|^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

media_root = Path(settings.MEDIA_ROOT)
media_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.MEDIA_URL_PREFIX, StaticFiles(directory=media_root), name="media")

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "AutoAssist AI Backend running"
    }
