"""Settings router – API key management, provider config, and connection testing."""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings, reload_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

# Project root .env path (same as main.py)
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_env_path = _project_root / ".env"
_env_example_path = _project_root / ".env.example"

# ---------------------------------------------------------------------------
# Allowed keys (whitelist)
# ---------------------------------------------------------------------------

ALLOWED_KEYS = {
    "ARK_API_KEY",
    "CLOUD_BASE_URL",
    "CLOUD_MODEL",
    "VOLCENGINE_CAPTION_APPID",
    "VOLCENGINE_CAPTION_TOKEN",
    "VOLCENGINE_CAPTION_BOOSTING_TABLE_ID",
    "VOLCENGINE_CAPTION_CORRECT_TABLE_ID",
}

# Key metadata for the frontend
KEY_METADATA = [
    {
        "key_name": "ARK_API_KEY",
        "display_name": "API Key",
        "group": "llm",
        "required": True,
        "description": "用于脚本匹配、SRT 分段和精剪决策的 LLM 服务密钥",
    },
    {
        "key_name": "CLOUD_BASE_URL",
        "display_name": "Base URL",
        "group": "llm",
        "required": False,
        "description": "LLM API 端点地址（留空使用默认值）",
    },
    {
        "key_name": "CLOUD_MODEL",
        "display_name": "模型名称",
        "group": "llm",
        "required": False,
        "description": "LLM 模型标识符（留空使用默认值）",
    },
    {
        "key_name": "VOLCENGINE_CAPTION_APPID",
        "display_name": "App ID",
        "group": "transcription",
        "required": True,
        "description": "火山引擎音视频字幕服务的应用 ID",
    },
    {
        "key_name": "VOLCENGINE_CAPTION_TOKEN",
        "display_name": "Token",
        "group": "transcription",
        "required": True,
        "description": "火山引擎音视频字幕服务的鉴权令牌",
    },
    {
        "key_name": "VOLCENGINE_CAPTION_BOOSTING_TABLE_ID",
        "display_name": "热词表 ID",
        "group": "transcription",
        "required": False,
        "description": "热词表 ID，用于提高专业术语的转录准确率（可选）",
    },
    {
        "key_name": "VOLCENGINE_CAPTION_CORRECT_TABLE_ID",
        "display_name": "替换词表 ID",
        "group": "transcription",
        "required": False,
        "description": "替换词表 ID，用于自动纠正转录中的常见错误（可选）",
    },
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ApiKeyStatus(BaseModel):
    key_name: str
    display_name: str
    group: str
    is_set: bool
    masked_value: str
    required: bool
    description: str


class ApiKeysResponse(BaseModel):
    keys: list[ApiKeyStatus]
    llm_base_url: str
    llm_model: str


class ApiKeyUpdate(BaseModel):
    key_name: str
    value: str


class UpdateKeysRequest(BaseModel):
    keys: list[ApiKeyUpdate]


class TestLlmRequest(BaseModel):
    api_key: str
    base_url: str
    model: str


class TestTranscriptionRequest(BaseModel):
    appid: str
    token: str


class TestResult(BaseModel):
    ok: bool
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_value(value: str) -> str:
    """Mask a secret value, showing only the last 4 characters."""
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]


def _get_current_value(key_name: str) -> str:
    """Get the current value of a config key from the settings singleton."""
    settings = get_settings()
    return str(getattr(settings, key_name, ""))


def _read_env_lines() -> list[str]:
    """Read the .env file as lines, or return empty list if missing."""
    if _env_path.exists():
        return _env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    # If .env doesn't exist but .env.example does, use it as a template
    if _env_example_path.exists():
        return _env_example_path.read_text(encoding="utf-8").splitlines(keepends=True)
    return []


def _write_env(updates: dict[str, str]) -> None:
    """
    Update .env file with the given key-value pairs.
    Preserves comments and non-target lines. Atomic write via tmp file.
    """
    lines = _read_env_lines()
    remaining_keys = dict(updates)  # keys we still need to write
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Skip empty lines and comments — preserve them
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Parse KEY=VALUE
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining_keys:
                new_lines.append(f"{key}={remaining_keys.pop(key)}\n")
                continue

        new_lines.append(line)

    # Append any keys that weren't found in existing file
    if remaining_keys:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        for key, value in remaining_keys.items():
            new_lines.append(f"{key}={value}\n")

    # Atomic write
    tmp_path = _env_path.with_suffix(".tmp")
    tmp_path.write_text("".join(new_lines), encoding="utf-8")
    os.replace(str(tmp_path), str(_env_path))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/keys", response_model=ApiKeysResponse)
async def get_keys():
    """Return the current status of all configurable API keys (masked)."""
    settings = get_settings()
    keys = []
    for meta in KEY_METADATA:
        value = _get_current_value(meta["key_name"])
        keys.append(ApiKeyStatus(
            key_name=meta["key_name"],
            display_name=meta["display_name"],
            group=meta["group"],
            is_set=bool(value),
            masked_value=_mask_value(value),
            required=meta["required"],
            description=meta["description"],
        ))

    return ApiKeysResponse(
        keys=keys,
        llm_base_url=settings.CLOUD_BASE_URL,
        llm_model=settings.CLOUD_MODEL,
    )


@router.put("/keys", response_model=ApiKeysResponse)
async def update_keys(req: UpdateKeysRequest):
    """Save API keys to .env and reload the settings singleton."""
    env_updates: dict[str, str] = {}

    for item in req.keys:
        if item.key_name not in ALLOWED_KEYS:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown key: {item.key_name}",
            )
        env_updates[item.key_name] = item.value

    if not env_updates:
        raise HTTPException(status_code=400, detail="No keys provided")

    # Write to .env
    _write_env(env_updates)

    # Sync os.environ so Pydantic can read updated values
    for key, value in env_updates.items():
        os.environ[key] = value

    # Reload settings singleton
    reload_settings()

    logger.info("Settings updated: %s", list(env_updates.keys()))
    return await get_keys()


@router.post("/test-llm", response_model=TestResult)
async def test_llm(req: TestLlmRequest):
    """Test LLM connection with the provided credentials (without saving)."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=req.api_key,
            base_url=req.base_url,
        )
        response = await client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        if response.choices:
            return TestResult(ok=True, message="LLM 连接成功")
        return TestResult(ok=False, message="LLM 返回了空响应")
    except Exception as e:
        logger.warning("LLM connection test failed: %s", e)
        return TestResult(ok=False, message=f"连接失败: {e}")


@router.post("/test-transcription", response_model=TestResult)
async def test_transcription(req: TestTranscriptionRequest):
    """Test Volcengine Caption API auth with the provided credentials."""
    try:
        import httpx

        # Use the submit endpoint with an empty/minimal request to test auth.
        # The API will reject the payload but return 401 if auth fails vs
        # a different error if auth succeeds.
        url = "https://openspeech.bytedance.com/api/v1/vc/submit"
        headers = {
            "Authorization": f"Bearer; {req.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "appid": req.appid,
            "language": "zh-CN",
            "file_url": "https://test-auth-only.invalid/test.wav",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)

        data = resp.json()
        # If we get a non-auth error, the credentials are valid
        # Auth failure typically returns specific error codes
        if resp.status_code == 401 or (isinstance(data, dict) and data.get("code") in (-1, 1001)):
            return TestResult(ok=False, message="鉴权失败，请检查 App ID 和 Token")

        # Any other response means auth passed (even if request itself is invalid)
        return TestResult(ok=True, message="转录服务鉴权成功")

    except Exception as e:
        logger.warning("Transcription auth test failed: %s", e)
        return TestResult(ok=False, message=f"连接失败: {e}")
