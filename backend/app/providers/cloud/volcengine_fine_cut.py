import json
import logging

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class VolcEngineFineCutDecider:
    """LLM decider for KEEP/REMOVE judgments inside a matched script window."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.ARK_API_KEY,
            base_url=settings.CLOUD_BASE_URL,
        )
        self.model = settings.CLOUD_MODEL

    @staticmethod
    def _parse_json_response(content: str) -> list[dict]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            end = len(lines) - 1
            while end > 0 and not lines[end].strip().startswith("```"):
                end -= 1
            content = "\n".join(lines[1:end])
        return json.loads(content)

    async def decide(
        self,
        *,
        script_text: str,
        transcript_chunks: list[dict],
        prev_script: str = "",
        next_script: str = "",
    ) -> list[dict]:
        chunk_lines = []
        for chunk in transcript_chunks:
            chunk_lines.append(
                f"[{chunk['idx']}] {chunk['text']} "
                f"({chunk['start_time']:.2f}s - {chunk['end_time']:.2f}s)"
            )

        context_lines = []
        if prev_script:
            context_lines.append(f"上一句脚本：{prev_script}")
        context_lines.append(f"当前脚本：{script_text}")
        if next_script:
            context_lines.append(f"下一句脚本：{next_script}")

        prompt = (
            "你是一位专业的视频剪辑师。请严格依据当前脚本，判断每个转录小片段是否应该保留。\n\n"
            "规则：\n"
            "1. 脚本是唯一标准，脚本里没有的内容就应该删除。\n"
            "2. 忽略 ASR 同音字或个别识别错误，按语义判断。\n"
            "3. REMOVE 的情况包括：脚本外补充、口误重说、重复表达、空话、未完成起句、无意义语气词。\n"
            "4. 如果拿不准，优先 KEEP，不要过度删除。\n\n"
            "脚本上下文：\n"
            f"{chr(10).join(context_lines)}\n\n"
            "待判断的转录小片段：\n"
            f"{chr(10).join(chunk_lines)}\n\n"
            "输出 JSON 数组，每项格式为："
            '[{"idx": 0, "action": "KEEP"|"REMOVE", "reason": "不超过12字"}]\n'
            "只返回 JSON，不要输出其他内容。"
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = response.choices[0].message.content.strip()
        decisions = self._parse_json_response(content)

        normalized: list[dict] = []
        valid_indices = {chunk["idx"] for chunk in transcript_chunks}
        for item in decisions:
            idx = item.get("idx")
            action = str(item.get("action", "")).upper()
            if idx not in valid_indices or action not in {"KEEP", "REMOVE"}:
                continue
            normalized.append(
                {
                    "idx": idx,
                    "action": action,
                    "reason": str(item.get("reason", "")),
                }
            )

        return normalized
