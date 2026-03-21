import logging

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.dictionary import DictionaryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["dictionary"])


def _get_dict_service() -> DictionaryService:
    settings = get_settings()
    return DictionaryService(settings.DICTIONARY_DIR)


@router.get("/dictionary")
async def get_dictionary():
    """Get the current dictionary."""
    service = _get_dict_service()
    return service.export_data()


@router.post("/dictionary/entry")
async def add_entry(wrong: str, correct: str, category: str = "general"):
    """Add a correction entry to the dictionary."""
    if not wrong or not correct:
        raise HTTPException(status_code=400, detail="Both 'wrong' and 'correct' are required")

    service = _get_dict_service()
    entry = service.add_entry(wrong, correct, category)
    return {
        "message": "Entry added",
        "entry": {
            "wrong": entry.wrong,
            "correct": entry.correct,
            "category": entry.category,
        },
    }


@router.delete("/dictionary/entry")
async def remove_entry(wrong: str):
    """Remove a correction entry from the dictionary."""
    if not wrong:
        raise HTTPException(status_code=400, detail="'wrong' parameter is required")

    service = _get_dict_service()
    if service.remove_entry(wrong):
        return {"message": "Entry removed", "wrong": wrong}
    raise HTTPException(status_code=404, detail=f"Entry '{wrong}' not found")


@router.post("/dictionary/import")
async def import_dictionary(data: dict):
    """Import dictionary data from JSON."""
    service = _get_dict_service()
    count = service.import_data(data)
    return {"message": f"Imported {count} entries", "count": count}


@router.get("/dictionary/export")
async def export_dictionary():
    """Export dictionary data as JSON."""
    service = _get_dict_service()
    return service.export_data()
