import logging
import os
import warnings
from pathlib import Path

# ---------------------------------------------------------------------------
# Early environment tweaks (before any heavy imports)
# ---------------------------------------------------------------------------

# Suppress matplotlib font-cache rebuild (~1.5 min on first import by
# pyannote / whisperx).  Setting MPLCONFIGDIR to a pre-existing writable
# dir avoids the expensive scan, and the Agg backend avoids any GUI toolkit.
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parent.parent / "data" / ".mpl_cache"),
)

# Suppress noisy torchcodec warning emitted by torchaudio / whisperx
warnings.filterwarnings("ignore", message=".*torchcodec.*")
# Suppress other common noisy warnings from ML dependencies
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")

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
from app.routers import alignment, dictionary, export, jobs, storage, system, upload

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
app.include_router(system.router)
app.include_router(storage.router)

# Mount static files for downloads
settings = get_settings()
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    # Ensure matplotlib cache dir exists so it never triggers a slow rebuild
    Path(os.environ.get("MPLCONFIGDIR", "")).mkdir(parents=True, exist_ok=True)

    # Trigger job manager init (restores persisted jobs)
    from app.jobs.manager import get_job_manager
    mgr = get_job_manager()
    logger.info("A-Roll Rough Cut Tool backend starting up")
    logger.info(f"Data directory: {settings.DATA_DIR}")
    logger.info(f"Restored {len(mgr.list_jobs())} jobs from disk")
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
