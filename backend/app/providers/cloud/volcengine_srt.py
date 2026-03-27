import json
import logging

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class SRTSegmentationError(RuntimeError):
    """Raised when SRT segmentation cannot be completed safely."""


class VolcEngineSRTSegmenter:
    """Use Doubao Seed to split subtitle text into readable SRT chunks."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.ARK_API_KEY,
            base_url=settings.CLOUD_BASE_URL,
        )
        self.model = settings.SRT_SEGMENTATION_MODEL
        self.batch_size = max(1, settings.SRT_SEGMENTATION_BATCH_SIZE)

    @staticmethod
    def _parse_json_response(content: str) -> list[dict]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            end = len(lines) - 1
            while end > 0 and not lines[end].strip().startswith("```"):
                end -= 1
            content = "\n".join(lines[1:end])
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            raise SRTSegmentationError("Seed 返回的 SRT 分段结果不是 JSON 数组")
        return parsed

    def _build_prompt(self, items: list[dict]) -> str:
        max_chars = get_settings().SRT_MAX_CHARS_PER_SEGMENT
        payload = json.dumps(items, ensure_ascii=False)
        return (
            "你是一名专业的中文字幕分段助手。"
            "请根据输入文本，将每条文字拆成适合 SRT 阅读的短段。\n\n"
            "硬性规则：\n"
            "1. 只能按原文切分，绝对不能增字、删字、改字、改标点。\n"
            "2. 必须保持原文顺序，所有分段拼接后要和原文完全一致。\n"
            "3. 优先按自然停顿、短语和语义边界切分。\n"
            f"4. 每段尽量不超过{max_chars}个汉字，必要时可略超，但禁止机械硬切。\n"
            f"5. 如果原文短于{max_chars}个字符，保留单段；否则必须分段。\n"
            "6. 只返回 JSON 数组，不要解释，不要 Markdown。\n\n"
            "输出格式：\n"
            '[{"id":0,"segments":["第一段","第二段"]}]\n\n'
            f"输入：\n{payload}"
        )

    async def segment_texts(self, texts: list[str]) -> list[list[str]]:
        if not texts:
            return []

        settings = get_settings()
        if not settings.ARK_API_KEY:
            raise SRTSegmentationError("未配置 ARK_API_KEY，无法使用 Seed 生成 SRT 分段")

        results: list[list[str] | None] = [None] * len(texts)

        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset:offset + self.batch_size]
            items = [
                {"id": batch_index, "text": text}
                for batch_index, text in enumerate(batch)
            ]
            prompt = self._build_prompt(items)

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    timeout=60,
                )
            except Exception as exc:
                raise SRTSegmentationError(f"Seed SRT 分段调用失败: {exc}") from exc

            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise SRTSegmentationError("Seed 没有返回任何 SRT 分段内容")

            try:
                parsed = self._parse_json_response(content)
            except Exception as exc:
                raise SRTSegmentationError(f"Seed 返回了无法解析的 SRT 分段结果: {exc}") from exc

            seen_ids: set[int] = set()
            for item in parsed:
                if not isinstance(item, dict):
                    raise SRTSegmentationError("Seed 返回的 SRT 分段项格式不正确")
                item_id = item.get("id")
                if not isinstance(item_id, int) or not (0 <= item_id < len(batch)):
                    raise SRTSegmentationError("Seed 返回了非法的 SRT 分段编号")
                segments = item.get("segments")
                if not isinstance(segments, list) or not segments:
                    raise SRTSegmentationError("Seed 返回的 SRT 分段列表为空或格式错误")
                if item_id in seen_ids:
                    raise SRTSegmentationError("Seed 返回了重复的 SRT 分段编号")
                seen_ids.add(item_id)
                results[offset + item_id] = segments

            if len(seen_ids) != len(batch):
                raise SRTSegmentationError("Seed 返回的 SRT 分段数量不完整")

        return [result for result in results if result is not None]
