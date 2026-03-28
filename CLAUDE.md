# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 第一性原理

永远使用第一性原理做这个项目。从用户实际使用场景倒推技术方案，不要按文档规范正推。

- 遇到 NLE 兼容性问题时，优先参考实际软件测试结果，而非 Apple/Adobe 文档规范
- 涉及中文文本匹配时，优先考虑 LLM 语义理解，字符串匹配只做兜底
- 当同一个问题反复出现时，说明根因没找对，需要换思路而非继续修补
- 思考起点永远是"用户最终要什么结果"，倒推出技术实现

## 可替换性原则

新增功能时，时刻记住项目中的每个组件都是可替换的，必须做抽象层。具体来说：

- 新增 provider（转录、匹配、导出等）时，先定义 ABC 接口，再写具体实现
- 不要把某个第三方服务的特有逻辑写死在业务代码里，通过抽象层隔离
- 现有的 Provider 模式（`providers/base.py` → `providers/config.py` 工厂）是标准做法，新功能应遵循同样的模式

## 实现策略 — 分阶段 Pipeline

非trivial的功能实现采用分阶段 pipeline，每个阶段有明确的输入输出和验证点：

1. **分析依赖关系** — 识别哪些任务互相独立、哪些有先后依赖
2. **独立任务并行** — 没有依赖的任务（如配置项、新模块、prompt修改）用多个 Agent 同时执行
3. **每阶段设 Checkpoint** — 阶段完成后打印输出，确认接口签名、配置命名、调用链一致后再进下一步
4. **依赖任务串行** — 有依赖的集成工作（如接入新模块、测试）等前置完成后再执行
5. **测试收尾** — 最后运行全量 pytest，确保无回归

原则：宁可多一个 checkpoint 暂停确认，也不要跳过验证直接推进。

## Project Overview

CutFlow — 口播视频智能粗剪工具。Takes a voiceover script (Markdown) + audio recording, aligns them via transcription and matching, lets the user review/edit segments in a web UI, then exports EDL/FCPXML/SRT timelines for Premiere, Final Cut Pro, DaVinci Resolve, and 剪映.

**Target users are non-technical video editors on Mac.** All UI text and comments should be accessible to this audience. The user does not have a coding background.

## Commands

```bash
# Setup (first time)
./setup.sh

# Start both backend + frontend
./start.sh                    # opens http://localhost:5173

# Backend only
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Tests
backend/.venv/bin/pytest backend/tests/
backend/.venv/bin/pytest backend/tests/test_alignment_engine.py  # single file
backend/.venv/bin/pytest backend/tests/test_fine_cut.py -k "test_name"  # single test

# Lint frontend
cd frontend && npm run lint
```

The Python venv lives at `backend/.venv/`. Always use `backend/.venv/bin/python` or `backend/.venv/bin/pytest`.

## Architecture

**Two-process app:** Python FastAPI backend (port 8000) + React/Vite frontend (port 5173). Vite proxies `/api/*` to the backend.

### Backend (`backend/app/`)

- **main.py** — FastAPI app, CORS, router registration, static file serving
- **config.py** — `Settings` dataclass with thresholds, model names, directories
- **routers/** — 8 routers: upload, jobs, alignment, export, dictionary, system, storage, settings
- **jobs/worker.py** — 8-stage async pipeline (parse → load → transcribe → match → pauses → align → optimize → generate). Each stage has a weight for progress calculation.
- **jobs/manager.py** — Job state machine (CREATED → TRANSCRIBING → MATCHING → ALIGNING → REVIEW → EXPORTING → DONE/ERROR). SSE progress streaming via `/api/jobs/:id/sse`.
- **providers/** — Pluggable transcription/matching backends:
  - `local/` — WhisperX transcriber, RapidFuzz matcher
  - `cloud/` — Volcengine Caption API (transcription), Volcengine LLM (matching, SRT segmentation, fine-cut)
  - `base.py` — ABC interfaces; `config.py` — factory functions
- **services/** — Business logic: alignment_engine, pause_processor, fine_cut, clip_optimizer, edl/fcpxml/srt generators, dictionary, script_parser, etc.
- **models/schemas.py** — Pydantic models. Key types: `AlignedSegment`, `TranscriptionResult`, `PauseSegment`, `JobState` enum, `SegmentStatus` enum, `ExportFormat` enum.

### Frontend (`frontend/src/`)

- **React 19 + TypeScript + Tailwind CSS 4 + Zustand**
- **App.tsx** — React Router with 7 pages: Upload → Processing → Review → Export + Dictionary, Storage, Settings
- **stores/jobStore.ts** — Zustand store with per-job state. User edits stored in `editedSegments`/`editedPauses` maps, layered on top of backend data. Fire-and-forget persistence.
- **api/client.ts** — API wrapper. Converts backend snake_case ↔ frontend camelCase.
- **hooks/useJob.ts** — Job lifecycle + SSE subscription.
- **components/** — Review UI (SegmentRow, AudioPlayer, TimelinePreview, ConfidenceBadge), Upload (FileDropZone), Layout (Header, Sidebar, Stepper)

### Data Flow

```
Upload (script.md + audio) → POST /api/upload → Background job
  → [8 stages with SSE progress] → AlignedSegment[]
  → Review UI (user edits) → POST /api/export/:id
  → EDL/FCPXML/SRT files in backend/data/outputs/{job_id}/
```

## Key Conventions

- **Language:** Primary use case is 中文口播 (Chinese voiceover). Script parsing, matching, and transcription are tuned for Mandarin. jieba for tokenization, RapidFuzz for fuzzy matching.
- **Provider pattern:** Transcription and matching each have local and cloud implementations behind an ABC. Factory in `providers/config.py`. Cloud uses Volcengine (火山引擎) APIs via the OpenAI-compatible client.
- **Script may start with hook sentences (钩子句):** These are "copy" segments reused from later in the video. Matching cannot assume script order equals timeline order.
- **API keys** are stored in `.env` (gitignored) and can be updated at runtime via the Settings page. Keys are reloaded on demand without restart.
- **Runtime data** goes to `backend/data/` — uploads, outputs, dictionary, jobs.json. All gitignored.
- **Frame rate** default is 29.97 fps (NTSC). Timecode conversions in both `frontend/src/utils/timecode.ts` and backend export generators.

## Environment

- `.env` at project root (copied from `.env.example` by setup.sh)
- Key vars: `ARK_API_KEY`, `CLOUD_BASE_URL`, `CLOUD_MODEL`, `VOLCENGINE_CAPTION_APPID`, `VOLCENGINE_CAPTION_TOKEN`
- The cloud API uses a **Volcengine Coding Plan** subscription (not standalone API). Base URL is specific to Coding Plan.

## 待修复的功能

已知问题和待改进功能记录在 [`backlog/README.md`](backlog/README.md)。发现新问题时，按索引格式添加到该文件中。

## 异地开发工作流

用户可能在不同的 Mac 电脑上工作（家里/公司）。代码通过 GitHub (`heyitseric/CutFlow`) 同步。

- `.env` 文件不在 Git 中，每台电脑需单独配置（参考 `.env.example`）
- `node_modules/` 和 `.venv/` 不在 Git 中，新电脑运行 `./setup.sh` 即可重建
- 首次在新电脑设置环境，参考 `SETUP-REMOTE.md`
