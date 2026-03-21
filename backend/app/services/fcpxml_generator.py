import logging
import xml.etree.ElementTree as ET
from fractions import Fraction

from app.models.schemas import AlignedSegment, SegmentStatus

logger = logging.getLogger(__name__)


def _frame_duration(frame_rate: float) -> tuple[int, int]:
    """Return (numerator, denominator) for frame duration as rational time."""
    if abs(frame_rate - 29.97) < 0.01:
        return (1001, 30000)
    elif abs(frame_rate - 23.976) < 0.01:
        return (1001, 24000)
    elif abs(frame_rate - 59.94) < 0.01:
        return (1001, 60000)
    else:
        fps = round(frame_rate)
        return (1, fps)


def _seconds_to_rational(seconds: float, frame_rate: float) -> str:
    """Convert seconds to FCPXML rational time string."""
    fd_num, fd_den = _frame_duration(frame_rate)

    # Convert to Fraction for exact arithmetic
    sec = Fraction(seconds).limit_denominator(1000000)
    frame_dur = Fraction(fd_num, fd_den)

    # Total frames (rounded)
    total_frames = round(float(sec / frame_dur))

    # Rational time = total_frames * fd_num / fd_den
    numerator = total_frames * fd_num

    return f"{numerator}/{fd_den}s"


def _duration_rational(duration: float, frame_rate: float) -> str:
    """Convert duration in seconds to rational time."""
    return _seconds_to_rational(duration, frame_rate)


def generate_fcpxml(
    segments: list[AlignedSegment],
    title: str = "A-Roll Rough Cut",
    frame_rate: float = 29.97,
    audio_filename: str = "audio.mp3",
    audio_duration: float = 0.0,
) -> str:
    """
    Generate FCPXML 1.11 for audio-only timeline.

    Uses Apple rational-time format with exact Fraction arithmetic.
    """
    fd_num, fd_den = _frame_duration(frame_rate)
    frame_dur_str = f"{fd_num}/{fd_den}s"

    # Root element
    fcpxml = ET.Element("fcpxml", version="1.11")

    # Resources
    resources = ET.SubElement(fcpxml, "resources")

    # Format resource
    format_el = ET.SubElement(resources, "format", {
        "id": "r1",
        "name": f"FFVideoFormat{round(frame_rate)}p",
        "frameDuration": frame_dur_str,
        "width": "1920",
        "height": "1080",
    })

    # Audio asset
    audio_dur_str = _seconds_to_rational(audio_duration, frame_rate) if audio_duration > 0 else "0/1s"
    asset = ET.SubElement(resources, "asset", {
        "id": "r2",
        "name": audio_filename,
        "src": f"file://./{audio_filename}",
        "start": "0/1s",
        "duration": audio_dur_str,
        "hasAudio": "1",
        "hasVideo": "0",
    })

    # Library > Event > Project > Sequence
    library = ET.SubElement(fcpxml, "library")
    event = ET.SubElement(library, "event", name=title)
    project = ET.SubElement(event, "project", name=title)

    # Calculate total duration
    active = [
        s for s in segments
        if s.status not in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED, SegmentStatus.REJECTED)
    ]
    active.sort(key=lambda s: s.script_index)

    total_duration = sum(s.end_time - s.start_time for s in active)
    total_dur_str = _seconds_to_rational(total_duration, frame_rate)

    sequence = ET.SubElement(project, "sequence", {
        "format": "r1",
        "duration": total_dur_str,
        "tcStart": "0/1s",
        "tcFormat": "DF" if abs(frame_rate - 29.97) < 0.01 else "NDF",
    })

    spine = ET.SubElement(sequence, "spine")

    # Add clips
    record_pos = 0.0
    for seg in active:
        duration = seg.end_time - seg.start_time
        if duration <= 0:
            continue

        offset_str = _seconds_to_rational(record_pos, frame_rate)
        start_str = _seconds_to_rational(seg.start_time, frame_rate)
        dur_str = _seconds_to_rational(duration, frame_rate)

        clip = ET.SubElement(spine, "asset-clip", {
            "ref": "r2",
            "offset": offset_str,
            "name": f"Segment {seg.script_index}",
            "start": start_str,
            "duration": dur_str,
            "audioRole": "dialogue",
        })

        # Add note for reordered segments
        if seg.is_reordered:
            note = ET.SubElement(clip, "note")
            note.text = f"REORDERED from position {seg.original_position}"

        record_pos += duration

    # Serialize to string
    ET.indent(fcpxml, space="  ")
    xml_str = ET.tostring(fcpxml, encoding="unicode", xml_declaration=True)
    # Add DOCTYPE
    xml_str = xml_str.replace(
        "<?xml version='1.0' encoding='us-ascii'?>",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>',
    )

    return xml_str
