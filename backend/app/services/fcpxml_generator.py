import logging
import os
import xml.etree.ElementTree as ET

from app.models.schemas import AlignedSegment, SegmentStatus

logger = logging.getLogger(__name__)


def _frame_duration_str(frame_rate: float) -> str:
    """Return frameDuration string for the <format> element.

    NTSC rates use canonical durations:
        29.97 fps -> 1001/30000s
        23.976 fps -> 1001/24000s
        59.94 fps -> 1001/60000s
    Integer rates use 1/<fps>s.
    """
    if abs(frame_rate - 29.97) < 0.01:
        return "1001/30000s"
    elif abs(frame_rate - 23.976) < 0.01:
        return "1001/24000s"
    elif abs(frame_rate - 59.94) < 0.01:
        return "1001/60000s"
    else:
        return f"1/{round(frame_rate)}s"


def _get_time_base(frame_rate: float) -> int:
    """Return the integer time base used for all clip timing strings.

    For NTSC rates, use the nearest integer fps (e.g. 29.97 -> 30).
    For integer rates, use the rate directly.
    """
    if abs(frame_rate - 29.97) < 0.01:
        return 30
    elif abs(frame_rate - 23.976) < 0.01:
        return 24
    elif abs(frame_rate - 59.94) < 0.01:
        return 60
    else:
        return round(frame_rate)


def seconds_to_frames(seconds: float, fps: float) -> int:
    """Convert seconds to frame count, matching the reference skill exactly."""
    return int(round(seconds * fps))


def generate_fcpxml(
    segments: list[AlignedSegment],
    title: str = "A-Roll Rough Cut",
    frame_rate: float = 29.97,
    audio_filename: str = "audio.mp3",
    audio_duration: float = 0.0,
    video_filename: str | None = None,
    buffer_duration: float = 0.0,
) -> str:
    """Generate FCPXML v1.11 for import into Final Cut Pro / JianYing.

    Structure matches the proven reference skill that works in JianYing:
    - version 1.11
    - format with name attribute
    - simple {frames}/{fps}s timing
    - asset-clip with format and tcFormat attributes
    """
    fps = _get_time_base(frame_rate)
    frame_dur_str = _frame_duration_str(frame_rate)

    # Always use a video asset so editors (e.g. JianYing) show exactly ONE
    # file to relink.
    if video_filename:
        media_filename = video_filename
    else:
        stem = audio_filename.rsplit(".", 1)[0] if "." in audio_filename else audio_filename
        media_filename = f"{stem}.mp4"

    source_name = os.path.splitext(media_filename)[0]
    source_total_frames = seconds_to_frames(audio_duration, fps) if audio_duration > 0 else 0

    # ── Root ──
    fcpxml = ET.Element("fcpxml", version="1.11")

    # ── Resources ──
    resources = ET.SubElement(fcpxml, "resources")

    # Format resource — includes name attribute for JianYing compatibility
    ET.SubElement(resources, "format", {
        "id": "r1",
        "name": f"FFVideoFormat1080p{fps}",
        "frameDuration": frame_dur_str,
        "width": "1920",
        "height": "1080",
    })

    # Media asset — src directly on <asset>, no <media-rep> child
    ET.SubElement(resources, "asset", {
        "id": "r2",
        "name": source_name,
        "src": f"file:///path/to/{media_filename}",
        "start": "0/1s",
        "duration": f"{source_total_frames}/{fps}s",
        "format": "r1",
        "hasVideo": "1",
        "hasAudio": "1",
        "audioSources": "1",
        "audioChannels": "2",
        "audioRate": "44100",
    })

    # ── Library > Event > Project > Sequence > Spine ──
    library = ET.SubElement(fcpxml, "library")
    event = ET.SubElement(library, "event", name="A-Roll Export")
    project = ET.SubElement(event, "project", name=title)

    # Filter to active segments in script order
    active = [
        s for s in segments
        if s.status not in (
            SegmentStatus.DELETED,
            SegmentStatus.UNMATCHED,
            SegmentStatus.REJECTED,
        )
    ]
    active.sort(key=lambda s: s.script_index)

    # Buffer is already applied by apply_buffer() in the pipeline.
    # Just clamp to valid range — do NOT re-apply buffer_duration here.
    buffered_segments: list[tuple[AlignedSegment, float, float]] = []
    for s in active:
        b_start = max(0.0, s.start_time)
        b_end = min(audio_duration, s.end_time) if audio_duration > 0 else s.end_time
        if b_end - b_start > 0:
            buffered_segments.append((s, b_start, b_end))

    total_duration = sum(end - start for _, start, end in buffered_segments)
    total_frames = seconds_to_frames(total_duration, fps)

    sequence = ET.SubElement(project, "sequence", {
        "format": "r1",
        "duration": f"{total_frames}/{fps}s",
        "tcStart": "0/1s",
        "tcFormat": "NDF",
    })

    spine = ET.SubElement(sequence, "spine")

    # ── Clips ──
    tl_offset = 0  # timeline offset in frames
    for i, (seg, b_start, b_end) in enumerate(buffered_segments):
        duration = b_end - b_start
        src_start = seconds_to_frames(b_start, fps)
        src_dur = seconds_to_frames(duration, fps)

        clip = ET.SubElement(spine, "asset-clip", {
            "name": f"{source_name} - Clip {i + 1}",
            "ref": "r2",
            "offset": f"{tl_offset}/{fps}s",
            "start": f"{src_start}/{fps}s",
            "duration": f"{src_dur}/{fps}s",
            "format": "r1",
            "tcFormat": "NDF",
        })

        # Add note for reordered segments
        if seg.is_reordered:
            note = ET.SubElement(clip, "note")
            note.text = f"REORDERED from position {seg.original_position}"

        tl_offset += src_dur

    # ── Serialize ──
    ET.indent(fcpxml, space="  ")
    xml_str = ET.tostring(fcpxml, encoding="unicode", xml_declaration=True)

    # Replace the default XML declaration with UTF-8 + DOCTYPE
    xml_str = xml_str.replace(
        "<?xml version='1.0' encoding='utf-8'?>",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>',
    )

    return xml_str
