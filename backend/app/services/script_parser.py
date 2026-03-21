import re

from app.models.schemas import ScriptSentence


# Patterns for Markdown stripping
_HEADER_PATTERN = re.compile(r"^#{1,6}\s+")
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_PATTERN = re.compile(r"\*(.+?)\*")
_BOLD_UNDERSCORE_PATTERN = re.compile(r"__(.+?)__")
_ITALIC_UNDERSCORE_PATTERN = re.compile(r"_(.+?)_")
_LINK_PATTERN = re.compile(r"\[(.+?)\]\(.+?\)")
_IMAGE_PATTERN = re.compile(r"!\[.*?\]\(.+?\)")
_CODE_PATTERN = re.compile(r"`(.+?)`")
_STRIKETHROUGH_PATTERN = re.compile(r"~~(.+?)~~")

# Chinese sentence endings
_CHINESE_SENTENCE_END = re.compile(r"([。！？])")
# English sentence endings (followed by space or end of string)
_ENGLISH_SENTENCE_END = re.compile(r"([.!?])(?:\s|$)")


def strip_markdown(text: str) -> str:
    """Remove Markdown formatting from text."""
    text = _IMAGE_PATTERN.sub("", text)
    text = _LINK_PATTERN.sub(r"\1", text)
    text = _BOLD_PATTERN.sub(r"\1", text)
    text = _ITALIC_PATTERN.sub(r"\1", text)
    text = _BOLD_UNDERSCORE_PATTERN.sub(r"\1", text)
    text = _ITALIC_UNDERSCORE_PATTERN.sub(r"\1", text)
    text = _CODE_PATTERN.sub(r"\1", text)
    text = _STRIKETHROUGH_PATTERN.sub(r"\1", text)
    text = _HEADER_PATTERN.sub("", text)
    # Remove list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    text = re.sub(r"^\s*\d+\.\s+", "", text)
    return text.strip()


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences based on Chinese and English punctuation."""
    if not text.strip():
        return []

    sentences = []
    # Split on Chinese sentence endings, keeping the punctuation
    parts = _CHINESE_SENTENCE_END.split(text)

    # Reassemble: parts alternate between text and punctuation
    current = ""
    for i, part in enumerate(parts):
        if _CHINESE_SENTENCE_END.match(part):
            current += part
            if current.strip():
                sentences.append(current.strip())
            current = ""
        else:
            current += part

    # Handle remaining text (no Chinese sentence ending)
    if current.strip():
        # Try splitting on English sentence endings
        eng_parts = _ENGLISH_SENTENCE_END.split(current)
        eng_current = ""
        for part in eng_parts:
            if _ENGLISH_SENTENCE_END.match(part + " "):
                eng_current += part
                if eng_current.strip():
                    sentences.append(eng_current.strip())
                eng_current = ""
            else:
                eng_current += part
        if eng_current.strip():
            sentences.append(eng_current.strip())

    return sentences


def parse_script(markdown_text: str) -> list[ScriptSentence]:
    """
    Parse a Markdown script into sentences.

    - Strips Markdown formatting
    - Splits on Chinese sentence endings (。！？)
    - Preserves paragraph boundaries (empty lines mark section starts)
    - Returns indexed ScriptSentence objects
    """
    lines = markdown_text.split("\n")
    result: list[ScriptSentence] = []
    index = 0
    is_section_start = True
    paragraph_buffer = ""

    for line in lines:
        stripped = line.strip()

        # Empty line = paragraph boundary
        if not stripped:
            # Flush buffer
            if paragraph_buffer.strip():
                plain = strip_markdown(paragraph_buffer)
                sentences = split_into_sentences(plain)
                for i, sentence in enumerate(sentences):
                    if sentence:
                        result.append(ScriptSentence(
                            index=index,
                            text=sentence,
                            is_section_start=is_section_start and i == 0,
                        ))
                        index += 1
                        is_section_start = False
            paragraph_buffer = ""
            is_section_start = True
            continue

        # Skip pure Markdown elements (horizontal rules, etc.)
        if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
            is_section_start = True
            continue

        # Accumulate paragraph text
        if paragraph_buffer:
            paragraph_buffer += " " + stripped
        else:
            paragraph_buffer = stripped

    # Flush remaining buffer
    if paragraph_buffer.strip():
        plain = strip_markdown(paragraph_buffer)
        sentences = split_into_sentences(plain)
        for i, sentence in enumerate(sentences):
            if sentence:
                result.append(ScriptSentence(
                    index=index,
                    text=sentence,
                    is_section_start=is_section_start and i == 0,
                ))
                index += 1
                is_section_start = False

    return result
