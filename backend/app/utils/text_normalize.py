import re
import unicodedata
from typing import Optional

import jieba


# Chinese punctuation to remove
_CHINESE_PUNCT = (
    "\u3000\u3001\u3002\u3003\u3008\u3009\u300a\u300b\u300c\u300d"
    "\u300e\u300f\u3010\u3011\u3014\u3015\u3016\u3017\u3018\u3019"
    "\u301a\u301b\u301c\u301d\u301e\u301f\u3020\uff01\uff02\uff03"
    "\uff04\uff05\uff06\uff07\uff08\uff09\uff0a\uff0b\uff0c\uff0d"
    "\uff0e\uff0f\uff1a\uff1b\uff1c\uff1d\uff1e\uff1f\uff20\uff3b"
    "\uff3c\uff3d\uff3e\uff3f\uff40\uff5b\uff5c\uff5d\uff5e"
    "\u2018\u2019\u201c\u201d\u2026\u2014\u2013"
)

_PUNCT_PATTERN = re.compile(
    rf"[{re.escape(_CHINESE_PUNCT)}\s!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{{|}}~]"
)

# Pattern for detecting Chinese characters
_CHINESE_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# Common abbreviations mapping
_ABBREVIATIONS = {
    "NMN": "NMN",
    "NAD+": "NAD+",
    "DNA": "DNA",
    "RNA": "RNA",
    "BMI": "BMI",
    "MCT": "MCT",
    "DHA": "DHA",
    "EPA": "EPA",
}


def clean_for_matching(text: str) -> str:
    """
    Unified text cleaning for all matching/alignment operations.

    Strips punctuation (Chinese + English), whitespace, and normalizes unicode.
    All matching-related modules should use this single function instead of
    maintaining their own cleaning regexes.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return _PUNCT_PATTERN.sub("", text)


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison:
    - Remove punctuation (Chinese and English)
    - Lowercase English
    - Strip extra whitespace
    """
    if not text:
        return ""

    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)

    # Remove punctuation
    text = _PUNCT_PATTERN.sub("", text)

    # Lowercase English portions
    result = []
    for char in text:
        if char.isascii() and char.isalpha():
            result.append(char.lower())
        else:
            result.append(char)

    return "".join(result).strip()


def tokenize_mixed(text: str) -> list[str]:
    """
    Tokenize mixed Chinese-English text:
    - Chinese text: use jieba segmentation
    - English words: keep intact
    """
    if not text:
        return []

    # First, normalize
    text = normalize_text(text)
    if not text:
        return []

    # Use jieba to tokenize (handles both Chinese and keeps English words)
    tokens = jieba.lcut(text)
    return [t.strip() for t in tokens if t.strip()]


def has_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(_CHINESE_CHAR_PATTERN.search(text))


def expand_abbreviations(text: str) -> str:
    """Expand common abbreviations (currently a no-op passthrough since
    abbreviations are kept as-is for matching purposes)."""
    return text


def chinese_char_count(text: str) -> int:
    """Count Chinese characters in text."""
    return len(_CHINESE_CHAR_PATTERN.findall(text))


def break_chinese_lines(text: str, max_chars: int = 18) -> list[str]:
    """
    Break Chinese text into lines with max_chars per line.
    Tries to break at natural boundaries (punctuation, spaces).
    """
    if not text:
        return []

    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    lines = []
    current = ""

    for char in text:
        current += char
        if len(current) >= max_chars:
            # Try to find a good break point
            break_at = -1
            for i in range(len(current) - 1, max(len(current) - 6, -1), -1):
                if current[i] in "，。！？、；：\u3000 ":
                    break_at = i + 1
                    break

            if break_at > 0:
                lines.append(current[:break_at].strip())
                current = current[break_at:]
            else:
                lines.append(current.strip())
                current = ""

    if current.strip():
        lines.append(current.strip())

    return lines
