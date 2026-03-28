# 待修复的功能

> 结构化追踪项目中发现的问题、缺陷和待改进功能。
> 每个条目记录在下方索引表中，详情可单独建文件放在本文件夹内。

## 索引

| ID | 标题 | 优先级 | 状态 | 发现日期 | 详情 |
|----|------|--------|------|----------|------|
| 001 | 服务配置页面无法清空已设置的 Key | 低 | 待修复 | 2026-03-27 | [详情](#001) |
| 002 | 云端 API 返回异常 JSON 时后端崩溃 | 高 | 已修复 | 2026-03-27 | [详情](#002) |
| 003 | 进度估算除零错误导致 NaN | 高 | 已修复 | 2026-03-27 | [详情](#003) |
| 004 | 处理页面加载失败时转圈不停止 | 高 | 已修复 | 2026-03-27 | [详情](#004) |
| 005 | 段落编辑保存可能写入错误任务 | 高 | 待修复 | 2026-03-27 | [详情](#005) |
| 006 | 转录服务遍历 words 时缺少空值检查 | 中 | 已修复 | 2026-03-27 | [详情](#006) |
| 007 | jobs.json 损坏时静默丢失全部任务历史 | 中 | 待修复 | 2026-03-27 | [详情](#007) |
| 008 | 任务列表加载失败无用户提示 | 中 | 待修复 | 2026-03-27 | [详情](#008) |
| 009 | 侧边栏 setInterval 组件卸载后未清理 | 中 | 待修复 | 2026-03-27 | [详情](#009) |
| 010 | 导出页面未防止导出中重复点击下载 | 中 | 待修复 | 2026-03-27 | [详情](#010) |
| 011 | 前端零测试覆盖 | 中 | 待改进 | 2026-03-27 | [详情](#011) |
| 012 | 后端路由层测试覆盖不足（仅 1/8） | 中 | 待改进 | 2026-03-27 | [详情](#012) |
| 013 | 云端 API 调用无重试/退避机制 | 低 | 待改进 | 2026-03-27 | [详情](#013) |
| 014 | FFmpeg 依赖未在启动时校验 | 低 | 待改进 | 2026-03-27 | [详情](#014) |
| 015 | 上传文件无进度反馈 | 低 | 待改进 | 2026-03-27 | [详情](#015) |
| 016 | 旧任务文件无自动清理机制 | 低 | 待改进 | 2026-03-27 | [详情](#016) |

---

## 详情

### 001

**标题：** 服务配置页面无法清空已设置的 Key

**发现日期：** 2026-03-27

**优先级：** 低

**状态：** 待修复

**描述：**
在「服务配置」页面中，用户无法通过 UI 清空一个已经设置的 API Key。原因是 `SettingsPage.tsx` 的 `handleSave()` 函数在收集 dirty 字段时跳过了空值：

```typescript
// frontend/src/pages/SettingsPage.tsx, handleSave()
for (const [keyName, value] of Object.entries(formValues)) {
  if (value !== '') {  // ← 空值被跳过，无法清空已有 key
    updates.push({ key_name: keyName, value });
  }
}
```

**影响：** 如果用户想移除某个 API Key（比如停用云端服务），只能手动编辑 `.env` 文件。

**建议修复方案：** 允许发送空值，后端 `_write_env` 将对应 key 设为空字符串（`KEY=`）。可以在 UI 加一个"清除"按钮或者允许用户提交空值。

**相关文件：**
- `frontend/src/pages/SettingsPage.tsx` — `handleSave()` 函数
- `backend/app/routers/settings.py` — `_write_env()` 函数

### 002

**标题：** 云端 API 返回异常 JSON 时后端崩溃

**发现日期：** 2026-03-27

**优先级：** 高

**状态：** 已修复

**描述：**
`volcengine.py` 的 `_parse_json_response()` 直接调用 `json.loads()`，没有 try/catch。当 LLM 返回非法 JSON（截断、多余文本等）时，异常未被捕获，直接导致整个任务失败且用户看到 500 错误。

**影响：** 云端匹配/SRT 分段时，LLM 偶尔返回格式异常的响应，会导致整个任务中断，用户需要从头重新开始。

**建议修复方案：** 在 `_parse_json_response()` 中加 `try/except json.JSONDecodeError`，尝试正则提取 JSON 块后重试解析，失败时抛出明确的业务异常（如 `MatchingError`），而非让原始异常冒泡。

**相关文件：**
- `backend/app/providers/cloud/volcengine.py` — `_parse_json_response()`

### 003

**标题：** 进度估算除零错误导致 NaN

**发现日期：** 2026-03-27

**优先级：** 高

**状态：** 已修复

**描述：**
`worker.py` 的 `_estimate_remaining()` 在 `progress <= 0.01` 时返回 None，但当 progress 恰好为 0.0 时，`elapsed / progress` 会除零。结果 NaN/Inf 传入 SSE 推送，前端进度条行为异常。

**影响：** 处理页面的"预计剩余时间"可能显示为 NaN 或不显示。

**建议修复方案：** 将条件改为 `progress <= 0.0` 或 `progress < 0.01`，确保 0.0 也被排除。同时在 `manager.py` 的 `_sanitize_float()` 中加日志，方便排查。

**相关文件：**
- `backend/app/jobs/worker.py` — `_estimate_remaining()`
- `backend/app/jobs/manager.py` — `_sanitize_float()`

### 004

**标题：** 处理页面加载失败时转圈不停止

**发现日期：** 2026-03-27

**优先级：** 高

**状态：** 已修复

**描述：**
`ProcessingPage.tsx` 的 `getJob()` 失败时，catch 块只做了 `console.error`，没有设置 error state。虽然组件有 error 状态变量（约第 424 行），但初始加载失败时不会触发，导致用户看到永远转圈的 loading 状态。

**影响：** 如果后端短暂不可用或接口超时，用户会一直看到加载动画，没有任何提示也没有重试按钮。

**建议修复方案：** 在 catch 块中 `setError(true)` 或设置一个 error message，展示「加载失败，请刷新页面」+ 重试按钮。

**相关文件：**
- `frontend/src/pages/ProcessingPage.tsx` — `getJob()` catch 块（约第 224-234 行）

### 005

**标题：** 段落编辑保存可能写入错误任务

**发现日期：** 2026-03-27

**优先级：** 高

**状态：** 待修复

**描述：**
`jobStore.ts` 的 `updateSegment()` 在保存失败后会用 `setTimeout` 2 秒重试。但重试时使用闭包中的 `jobId`，如果用户在这 2 秒内切换了任务，重试会把编辑写到旧任务上。

**影响：** 快速切换任务时，用户的编辑可能被写到错误的任务中，且无任何提示。

**建议修复方案：** 重试前检查 `get().activeJobId === jobId`，不匹配则丢弃重试。或者改用 AbortController 在任务切换时取消所有 pending 操作。

**相关文件：**
- `frontend/src/stores/jobStore.ts` — `updateSegment()` 重试逻辑（约第 287-297 行）

### 006

**标题：** 转录服务遍历 words 时缺少空值检查

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 已修复

**描述：**
`transcription.py` 和 `fine_cut.py` 中遍历 `transcription.segments` 和 `segment.words` 时，没有对 None 做防御。如果转录结果中某个 segment 的 words 为空（WhisperX 偶尔会出现），会抛 TypeError。

**影响：** 特定音频文件（如静音片段较多的录音）处理时可能崩溃。

**建议修复方案：** 在遍历前加 `for seg in (transcription.segments or [])` 和 `for w in (seg.words or [])`。

**相关文件：**
- `backend/app/services/transcription.py` — 字典校正循环（约第 76-83 行）
- `backend/app/services/fine_cut.py` — `_flatten_words()`（约第 60-71 行）

### 007

**标题：** jobs.json 损坏时静默丢失全部任务历史

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 待修复

**描述：**
`persistence.py` 读取 `jobs.json` 时，如果文件损坏（非法 JSON），catch 块会返回空字典，相当于丢弃全部历史记录且无任何用户警告。

**影响：** 异常断电或磁盘写入中断后，用户可能丢失所有任务历史，侧边栏变空，无法恢复。

**建议修复方案：** 1) 写入时先写临时文件再原子替换（`os.replace`）；2) 读取失败时保留 `.bak` 备份并提示用户；3) 加日志记录损坏事件。

**相关文件：**
- `backend/app/jobs/persistence.py` — JSON 读取逻辑（约第 108-114 行）

### 008

**标题：** 任务列表加载失败无用户提示

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 待修复

**描述：**
`jobStore.ts` 的 `fetchJobList()` 在 catch 中注释写了 "Silently ignore"，网络请求失败时侧边栏显示为空白，用户无法区分"没有任务"和"加载失败"。

**影响：** 后端短暂不可用时，用户误以为任务全部丢失。

**建议修复方案：** 加一个 `fetchError` 状态，在侧边栏显示"加载失败，点击重试"。

**相关文件：**
- `frontend/src/stores/jobStore.ts` — `fetchJobList()`（约第 208-210 行）
- `frontend/src/components/layout/Sidebar.tsx` — 任务列表渲染

### 009

**标题：** 侧边栏 setInterval 组件卸载后未清理

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 待修复

**描述：**
`Sidebar.tsx` 中有 `setInterval()` 调用（约第 319-339 行），如果用户快速切换页面导致组件反复挂载/卸载，interval 清理可能不及时，导致多个 interval 同时运行。

**影响：** 长时间使用后可能出现内存泄漏和不必要的网络请求。

**建议修复方案：** 确保 `useEffect` 的 cleanup 函数可靠地 `clearInterval`；或改用 `setTimeout` 递归调用模式，避免 interval 堆积。

**相关文件：**
- `frontend/src/components/layout/Sidebar.tsx` — setInterval 逻辑（约第 319-339 行）

### 010

**标题：** 导出页面未防止导出中重复点击下载

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 待修复

**描述：**
`ExportPage.tsx` 在导出进行中时，`readyFormats` 列表可能已部分填充，用户可以点击尚未完成的格式的下载按钮。

**影响：** 导出中点击下载可能触发错误或下载到不完整的文件。

**建议修复方案：** 导出进行时 disable 所有下载按钮，或对每个格式单独显示导出状态（进行中/已完成/失败）。

**相关文件：**
- `frontend/src/pages/ExportPage.tsx` — 下载按钮区域（约第 291-312 行）

### 011

**标题：** 前端零测试覆盖

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 待改进

**描述：**
`frontend/src/` 下没有任何测试文件，也没有配置 Vitest 或 Jest 等测试框架。关键交互逻辑（如 jobStore 状态管理、timecode 转换工具函数、API 调用）完全没有测试保障。

**影响：** 前端改动无法自动验证是否引入回归，只能靠手动测试。

**建议修复方案：**
1. 配置 Vitest（与 Vite 生态一致）
2. 优先为 `utils/timecode.ts`（纯函数）和 `stores/jobStore.ts`（核心状态）写单测
3. 关键页面（ReviewPage、ProcessingPage）加组件级快照测试

**相关文件：**
- `frontend/package.json` — 需添加 vitest 依赖和 test script
- `frontend/src/utils/timecode.ts` — 优先测试目标
- `frontend/src/stores/jobStore.ts` — 优先测试目标

### 012

**标题：** 后端路由层测试覆盖不足（仅 1/8）

**发现日期：** 2026-03-27

**优先级：** 中

**状态：** 待改进

**描述：**
8 个路由中仅 `export` 路由有测试。upload、jobs、alignment、storage、system、dictionary、settings 路由均无测试。多个核心服务（script_parser、pause_processor、edl_generator、fcpxml_generator）也缺少测试。

**影响：** API 行为变更无法自动检测，端到端工作流无回归保障。

**建议修复方案：**
1. 用 `httpx.AsyncClient` + `app` 写路由级集成测试
2. 优先覆盖 upload（文件校验）和 jobs（状态机流转）
3. 为 edl_generator 和 fcpxml_generator 加输出格式校验测试

**相关文件：**
- `backend/tests/` — 现有 12 个测试文件
- `backend/app/routers/` — 8 个路由模块

### 013

**标题：** 云端 API 调用无重试/退避机制

**发现日期：** 2026-03-27

**优先级：** 低

**状态：** 待改进

**描述：**
火山引擎 Caption API 和 LLM API 在遇到 5xx 或网络超时时直接失败，没有自动重试和指数退避。偶发的网络抖动会导致整个任务中断。

**影响：** 网络不稳定时（如 Wi-Fi 切换、ISP 波动），云端模式下任务失败率偏高。

**建议修复方案：** 在 `volcengine_caption.py` 的 `_poll()` 和 `volcengine.py` 的 API 调用处加入重试逻辑（3 次，指数退避 1s/2s/4s），可用 `tenacity` 库或手写。

**相关文件：**
- `backend/app/providers/cloud/volcengine_caption.py` — `_submit()` / `_poll()`
- `backend/app/providers/cloud/volcengine.py` — LLM API 调用

### 014

**标题：** FFmpeg 依赖未在启动时校验

**发现日期：** 2026-03-27

**优先级：** 低

**状态：** 待改进

**描述：**
FFmpeg 是音频处理的关键依赖，但只在 `setup.sh` 安装时检查。后端启动时不校验 FFmpeg 是否可用，直到实际运行 clip_optimizer 才会失败——此时任务已经走了大半流程。

**影响：** FFmpeg 被卸载或 PATH 丢失时，用户要等到处理后期才发现失败，之前的转录和匹配工作白费。

**建议修复方案：** 在 `main.py` 的 `lifespan` 中加一个 `shutil.which("ffmpeg")` 检查，不存在时在启动日志中警告。

**相关文件：**
- `backend/app/main.py` — lifespan startup
- `backend/app/services/silence_utils.py` — FFmpeg 调用点

### 015

**标题：** 上传文件无进度反馈

**发现日期：** 2026-03-27

**优先级：** 低

**状态：** 待改进

**描述：**
`client.ts` 的上传超时设为 5 分钟，但上传过程中没有进度条或百分比反馈。大文件（如 1 小时录音 > 500MB）上传时，用户只能看到一个静态的"上传中"提示，不知道是卡住还是在传。

**影响：** 大文件上传体验差，用户可能以为卡死而刷新页面导致上传中断。

**建议修复方案：** 用 `XMLHttpRequest` 或 `fetch` + `ReadableStream` 实现上传进度回调，在 UploadPage 显示进度条。

**相关文件：**
- `frontend/src/api/client.ts` — upload 函数（约第 51-76 行）
- `frontend/src/pages/UploadPage.tsx` — 上传 UI

### 016

**标题：** 旧任务文件无自动清理机制

**发现日期：** 2026-03-27

**优先级：** 低

**状态：** 待改进

**描述：**
`backend/data/uploads/` 和 `backend/data/outputs/` 中的文件在任务完成后永久保留。长期使用会积累大量音频文件占用磁盘空间，只能通过 UI 手动删除或运行 uninstall 脚本。

**影响：** 频繁使用的用户磁盘空间会被大量旧音频文件占满。

**建议修复方案：** 1) 在存储管理页面加"清理 X 天前的任务"功能；2) 或在配置中加一个自动清理阈值（如保留最近 30 天或最近 50 个任务）。

**相关文件：**
- `backend/app/routers/storage.py` — 存储管理接口
- `backend/app/config.py` — 可加清理相关配置项
