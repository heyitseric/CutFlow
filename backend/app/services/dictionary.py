import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import jieba

from app.models.schemas import DictionaryData, DictionaryEntry

logger = logging.getLogger(__name__)


class DictionaryService:
    def __init__(self, dictionary_dir: Path):
        self.dictionary_dir = dictionary_dir
        self.dict_path = dictionary_dir / "user_dict.json"
        self._data: Optional[DictionaryData] = None

    def load(self) -> DictionaryData:
        """Load dictionary from JSON file."""
        if self._data is not None:
            return self._data

        if not self.dict_path.exists():
            self._data = DictionaryData(version="1.0", entries=[], custom_terms=[])
            self.save()
            return self._data

        try:
            raw = json.loads(self.dict_path.read_text(encoding="utf-8"))
            entries = []
            for e in raw.get("entries", []):
                entries.append(DictionaryEntry(
                    wrong=e["wrong"],
                    correct=e["correct"],
                    category=e.get("category", "general"),
                    added_at=datetime.fromisoformat(e["added_at"]) if "added_at" in e else datetime.now(),
                    frequency=e.get("frequency", 0),
                ))
            self._data = DictionaryData(
                version=raw.get("version", "1.0"),
                entries=entries,
                custom_terms=raw.get("custom_terms", []),
            )
            return self._data
        except Exception as e:
            logger.error(f"Failed to load dictionary: {e}")
            self._data = DictionaryData(version="1.0", entries=[], custom_terms=[])
            return self._data

    def save(self) -> None:
        """Save dictionary to JSON file."""
        if self._data is None:
            return

        data = {
            "version": self._data.version,
            "entries": [
                {
                    "wrong": e.wrong,
                    "correct": e.correct,
                    "category": e.category,
                    "added_at": e.added_at.isoformat(),
                    "frequency": e.frequency,
                }
                for e in self._data.entries
            ],
            "custom_terms": self._data.custom_terms,
        }

        self.dictionary_dir.mkdir(parents=True, exist_ok=True)
        self.dict_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_entry(self, wrong: str, correct: str, category: str = "general") -> DictionaryEntry:
        """Add a correction entry."""
        data = self.load()

        # Check if entry already exists
        for entry in data.entries:
            if entry.wrong == wrong:
                entry.correct = correct
                entry.category = category
                self.save()
                return entry

        entry = DictionaryEntry(
            wrong=wrong,
            correct=correct,
            category=category,
            added_at=datetime.now(),
            frequency=0,
        )
        data.entries.append(entry)
        self.save()

        # Add to jieba
        jieba.add_word(correct)

        return entry

    def remove_entry(self, wrong: str) -> bool:
        """Remove a correction entry by its 'wrong' key."""
        data = self.load()
        original_len = len(data.entries)
        data.entries = [e for e in data.entries if e.wrong != wrong]
        if len(data.entries) < original_len:
            self.save()
            return True
        return False

    def increment_frequency(self, wrong: str) -> None:
        """Increment the usage frequency of a correction entry."""
        data = self.load()
        for entry in data.entries:
            if entry.wrong == wrong:
                entry.frequency += 1
                self.save()
                return

    def add_custom_term(self, term: str) -> None:
        """Add a custom term to the dictionary."""
        data = self.load()
        if term not in data.custom_terms:
            data.custom_terms.append(term)
            self.save()
            jieba.add_word(term)

    def remove_custom_term(self, term: str) -> bool:
        """Remove a custom term."""
        data = self.load()
        if term in data.custom_terms:
            data.custom_terms.remove(term)
            self.save()
            return True
        return False

    def apply_corrections(self, text: str) -> str:
        """Apply all dictionary corrections to text."""
        data = self.load()
        for entry in data.entries:
            if entry.wrong in text:
                text = text.replace(entry.wrong, entry.correct)
                self.increment_frequency(entry.wrong)
        return text

    def inject_into_jieba(self) -> None:
        """Load all custom terms and corrections into jieba."""
        data = self.load()
        for term in data.custom_terms:
            jieba.add_word(term)
        for entry in data.entries:
            jieba.add_word(entry.correct)
        logger.info(
            f"Injected {len(data.custom_terms)} terms and "
            f"{len(data.entries)} corrections into jieba"
        )

    def import_data(self, import_data: dict) -> int:
        """Import dictionary data from JSON. Returns number of entries imported."""
        data = self.load()
        count = 0

        for e in import_data.get("entries", []):
            existing = next((x for x in data.entries if x.wrong == e.get("wrong")), None)
            if existing:
                existing.correct = e.get("correct", existing.correct)
                existing.category = e.get("category", existing.category)
            else:
                data.entries.append(DictionaryEntry(
                    wrong=e["wrong"],
                    correct=e["correct"],
                    category=e.get("category", "general"),
                    added_at=datetime.now(),
                    frequency=0,
                ))
            count += 1

        for term in import_data.get("custom_terms", []):
            if term not in data.custom_terms:
                data.custom_terms.append(term)

        self.save()
        self.inject_into_jieba()
        return count

    def export_data(self) -> dict:
        """Export dictionary data as JSON-serializable dict."""
        data = self.load()
        return {
            "version": data.version,
            "entries": [
                {
                    "wrong": e.wrong,
                    "correct": e.correct,
                    "category": e.category,
                    "added_at": e.added_at.isoformat(),
                    "frequency": e.frequency,
                }
                for e in data.entries
            ],
            "custom_terms": data.custom_terms,
        }
