"""System resource monitoring endpoint."""

import platform
import subprocess
import logging
from typing import Optional

import psutil
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


def _get_gpu_info_darwin() -> dict:
    """Get GPU info on macOS."""
    gpu_name: Optional[str] = None
    gpu_percent: Optional[float] = None
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None

    is_apple_silicon = platform.machine() == "arm64"

    # Get GPU name via system_profiler
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-detailLevel", "basic"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Chipset Model:"):
                    gpu_name = stripped.split(":", 1)[1].strip()
                    break
    except Exception as e:
        logger.debug("Failed to get GPU name via system_profiler: %s", e)

    if is_apple_silicon:
        if not gpu_name:
            gpu_name = "Apple Silicon GPU"
        # On Apple Silicon, GPU shares unified memory.
        # Use memory pressure as a rough proxy — not a true GPU utilization
        # metric, but gives a sense of unified memory contention.
        try:
            result = subprocess.run(
                ["memory_pressure"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse "System-wide memory free percentage: XX%"
                for line in result.stdout.splitlines():
                    if "System-wide memory free percentage:" in line:
                        parts = line.split(":")
                        if len(parts) == 2:
                            pct_str = parts[1].strip().rstrip("%")
                            try:
                                free_pct = float(pct_str)
                                # Memory pressure = 100 - free%
                                gpu_percent = round(100.0 - free_pct, 1)
                            except ValueError:
                                pass
                        break
        except Exception as e:
            logger.debug("Failed to get memory_pressure: %s", e)

    return {
        "gpu_name": gpu_name,
        "gpu_percent": gpu_percent,
        "gpu_memory_used_gb": gpu_memory_used_gb,
        "gpu_memory_total_gb": gpu_memory_total_gb,
    }


def _get_gpu_info_windows() -> dict:
    """Get GPU info on Windows via nvidia-smi."""
    gpu_name: Optional[str] = None
    gpu_percent: Optional[float] = None
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None

    # Try nvidia-smi first
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpu_percent = float(parts[0])
                gpu_memory_used_gb = round(float(parts[1]) / 1024, 2)
                gpu_memory_total_gb = round(float(parts[2]) / 1024, 2)
                gpu_name = parts[3]
    except FileNotFoundError:
        logger.debug("nvidia-smi not found")
    except Exception as e:
        logger.debug("Failed to get GPU info via nvidia-smi: %s", e)

    # Fallback: try WMI for GPU name
    if gpu_name is None:
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = [
                    l.strip()
                    for l in result.stdout.strip().splitlines()
                    if l.strip() and l.strip().lower() != "name"
                ]
                if lines:
                    gpu_name = lines[0]
        except Exception as e:
            logger.debug("Failed to get GPU name via WMI: %s", e)

    return {
        "gpu_name": gpu_name,
        "gpu_percent": gpu_percent,
        "gpu_memory_used_gb": gpu_memory_used_gb,
        "gpu_memory_total_gb": gpu_memory_total_gb,
    }


@router.get("/stats")
async def system_stats():
    """Return current system resource usage."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # Memory
    mem = psutil.virtual_memory()
    memory_used_gb = round(mem.used / (1024**3), 1)
    memory_total_gb = round(mem.total / (1024**3), 1)
    memory_percent = round(mem.percent, 1)

    # GPU (platform-specific)
    sys_platform = platform.system().lower()
    if sys_platform == "darwin":
        gpu_info = _get_gpu_info_darwin()
        plat = "darwin"
    elif sys_platform == "windows":
        gpu_info = _get_gpu_info_windows()
        plat = "win32"
    else:
        gpu_info = {
            "gpu_name": None,
            "gpu_percent": None,
            "gpu_memory_used_gb": None,
            "gpu_memory_total_gb": None,
        }
        plat = sys_platform

    return {
        "cpu_percent": cpu_percent,
        "memory_used_gb": memory_used_gb,
        "memory_total_gb": memory_total_gb,
        "memory_percent": memory_percent,
        "gpu_name": gpu_info["gpu_name"],
        "gpu_percent": gpu_info["gpu_percent"],
        "gpu_memory_used_gb": gpu_info["gpu_memory_used_gb"],
        "gpu_memory_total_gb": gpu_info["gpu_memory_total_gb"],
        "platform": plat,
    }
