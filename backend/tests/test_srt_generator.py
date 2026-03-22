from app.models.schemas import ExportClip
from app.services.srt_generator import generate_srt


def test_generate_srt_merges_split_clips_for_same_sentence():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句台词",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=12.0,
            end_time=13.5,
            script_text="第一句台词",
        ),
        ExportClip(
            script_index=1,
            clip_index=0,
            start_time=20.0,
            end_time=21.0,
            script_text="第二句台词",
        ),
    ]

    srt = generate_srt(segments)

    assert srt.count("第一句台词") == 1
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "00:00:02,500 --> 00:00:03,500" in srt


def test_generate_srt_keeps_fine_cut_clauses_separate():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句，",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=12.0,
            end_time=13.0,
            script_text="第二句。",
        ),
    ]

    srt = generate_srt(segments)

    assert "00:00:00,000 --> 00:00:01,000" in srt
    assert "00:00:01,000 --> 00:00:02,000" in srt
    assert srt.count("第一句，") == 1
    assert srt.count("第二句。") == 1


def test_generate_srt_joins_transcript_text_across_split_clips():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句台词",
            transcript_text="第一句",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=11.0,
            end_time=12.5,
            script_text="第一句台词",
            transcript_text="台词",
        ),
    ]

    srt = generate_srt(segments, text_source="transcript")

    assert srt.count("第一句台词") == 1
    assert "第一句\n台词" not in srt
    assert "第一句台词" in srt
    assert "00:00:00,000 --> 00:00:02,500" in srt


def test_generate_srt_deduplicates_identical_transcript_text_for_split_clips():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句台词",
            transcript_text="第一句台词",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=11.0,
            end_time=12.0,
            script_text="第一句台词",
            transcript_text="第一句台词",
        ),
    ]

    srt = generate_srt(segments, text_source="transcript")

    assert srt.count("第一句台词") == 1
    assert "00:00:00,000 --> 00:00:02,000" in srt
