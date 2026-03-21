import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env from project root (two levels up from app/)
_project_root = Path(__file__).resolve().parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from app.config import get_settings
from app.routers import alignment, dictionary, export, jobs, upload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="A-Roll Rough Cut Tool",
    description="Backend for automated A-Roll rough cut editing",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(alignment.router)
app.include_router(export.router)
app.include_router(dictionary.router)

# Mount static files for downloads
settings = get_settings()
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    logger.info("A-Roll Rough Cut Tool backend starting up")
    logger.info(f"Data directory: {settings.DATA_DIR}")
    logger.info(f"Cloud provider: {settings.CLOUD_PROVIDER}")
    if settings.ARK_API_KEY:
        logger.info("ARK API key configured")
    else:
        logger.info("No ARK API key (cloud features disabled)")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "cloud_provider": settings.CLOUD_PROVIDER,
        "has_api_key": bool(settings.ARK_API_KEY),
    }
