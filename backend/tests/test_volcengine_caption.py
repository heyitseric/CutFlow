import app.config as config_module
from app.providers.config import get_transcriber
from app.providers.cloud.volcengine_caption import VolcengineCaptionTranscriber


def test_build_submit_params_without_optional_tables():
    transcriber = VolcengineCaptionTranscriber(appid="123", token="token")

    params = transcriber._build_submit_params("zh")

    assert params == {
        "appid": "123",
        "language": "zh-CN",
        "use_itn": "True",
        "use_punc": "True",
        "caption_type": "speech",
        "use_ddc": "True",
        "words_per_line": "15",
        "max_lines": "1",
    }


def test_build_submit_params_with_hotword_and_correct_tables():
    transcriber = VolcengineCaptionTranscriber(
        appid="123",
        token="token",
        boosting_table_id="boosting-table",
        correct_table_id="correct-table",
    )

    params = transcriber._build_submit_params("zh")

    assert params["asr_appid"] == "123"
    assert params["boosting_table_id"] == "boosting-table"
    assert params["id"] == "correct-table"


def test_get_transcriber_passes_optional_caption_tables(monkeypatch):
    config_module._settings = None
    monkeypatch.setenv("VOLCENGINE_CAPTION_APPID", "123")
    monkeypatch.setenv("VOLCENGINE_CAPTION_TOKEN", "token")
    monkeypatch.setenv("VOLCENGINE_CAPTION_BOOSTING_TABLE_ID", "boosting-table")
    monkeypatch.setenv("VOLCENGINE_CAPTION_CORRECT_TABLE_ID", "correct-table")

    transcriber = get_transcriber(provider="volcengine")

    assert isinstance(transcriber, VolcengineCaptionTranscriber)
    assert transcriber.boosting_table_id == "boosting-table"
    assert transcriber.correct_table_id == "correct-table"

    config_module._settings = None
