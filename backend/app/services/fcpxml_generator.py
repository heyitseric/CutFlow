import logging
import xml.etree.ElementTree as ET
from fractions import Fraction

from app.models.schemas import AlignedSegment, SegmentStatus

logger = logging.getLogger(__name__)


def _frame_duration(frame_rate: float) -> tuple[int, int]:
    """Return (numerator, denominator) for frame duration as rational time.

    For NTSC rates the canonical durations are:
        29.97 fps -> 1001/30000 s
        23.976 fps -> 1001/24000 s
        59.94 fps -> 1001/60000 s
    Integer rates use 1/<fps> s.
    """
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
    """Convert seconds to FCPXML rational time string.

    Example: 15.0 s at 30 fps -> "450/30s" (= 15.0 s expressed as
    frame-count * frame-duration-numerator / denominator).
    """
    if seconds <= 0:
        return "0/1s"

    fd_num, fd_den = _frame_duration(frame_rate)

    # Convert to Fraction for exact arithmetic
    sec = Fraction(seconds).limit_denominator(1000000)
    frame_dur = Fraction(fd_num, fd_den)

    # Total frames (rounded to nearest)
    total_frames = round(float(sec / frame_dur))

    # Rational time = total_frames * fd_num / fd_den
    numerator = total_frames * fd_num

    return f"{numerator}/{fd_den}s"


def _apply_buffer(
    start: float,
    end: float,
    buffer_duration: float,
    audio_duration: float,
) -> tuple[float, float]:
    """Extend segment boundaries by buffer_duration, clamped to valid range."""
    buffered_start = max(0.0, start - buffer_duration)
    buffered_end = min(audio_duration, end + buffer_duration) if audio_duration > 0 else end + buffer_duration
    return buffered_start, buffered_end


def generate_fcpxml(
    segments: list[AlignedSegment],
    title: str = "A-Roll Rough Cut",
    frame_rate: float = 29.97,
    audio_filename: str = "audio.mp3",
    audio_duration: float = 0.0,
    video_filename: str | None = None,
    buffer_duration: float = 0.0,
) -> str:
    """Generate FCPXML v1.9 for import into Final Cut Pro / JianYing.

    Structure (v1.9, widely supported):

        <fcpxml version="1.9">
          <resources>
            <format id="r1" .../>
            <asset id="r2" ...>
              <media-rep kind="original-media" src="..."/>
            </asset>
          </resources>
          <library>
            <event name="...">
              <project name="...">
                <sequence format="r1" duration="...">
                  <spine>
                    <asset-clip ref="r2" offset="..." start="..." duration="..."/>
                    ...
                  </spine>
                </sequence>
              </project>
            </event>
          </library>
        </fcpxml>

    Each aligned segment becomes an asset-clip on the spine.
    - `start`    = source IN point (where in the original media)
    - `duration` = clip length
    - `offset`   = position on the output timeline (cumulative)

    When video_filename is provided, the asset references a video file
    with hasVideo="1" so FCP can relink to the actual footage.
    """
    fd_num, fd_den = _frame_duration(frame_rate)
    frame_dur_str = f"{fd_num}/{fd_den}s"

    # Always use a video asset so editors (e.g. JianYing) show exactly ONE
    # file to relink.  Derive the video filename from the audio filename
    # when the caller didn't supply one.
    if video_filename:
        media_filename = video_filename
    else:
        stem = audio_filename.rsplit(".", 1)[0] if "." in audio_filename else audio_filename
        media_filename = f"{stem}.mp4"

    # ── Root ──
    fcpxml = ET.Element("fcpxml", version="1.9")

    # ── Resources ──
    resources = ET.SubElement(fcpxml, "resources")

    # Format resource (video dimensions are required even for audio-only)
    ET.SubElement(resources, "format", {
        "id": "r1",
        "frameDuration": frame_dur_str,
        "width": "1920",
        "height": "1080",
    })

    # Media asset — use <media-rep> child for the file reference
    media_dur_str = (
        _seconds_to_rational(audio_duration, frame_rate)
        if audio_duration > 0
        else "0/1s"
    )
    asset_attrs = {
        "id": "r2",
        "name": media_filename,
        "start": "0/1s",
        "duration": media_dur_str,
        "hasAudio": "1",
        "hasVideo": "1",
        "format": "r1",
    }

    asset = ET.SubElement(resources, "asset", asset_attrs)
    ET.SubElement(asset, "media-rep", {
        "kind": "original-media",
        "src": f"file://./{media_filename}",
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

    # Apply buffer and compute total duration
    buffered_segments: list[tuple[AlignedSegment, float, float]] = []
    for s in active:
        b_start, b_end = _apply_buffer(s.start_time, s.end_time, buffer_duration, audio_duration)
        if b_end - b_start > 0:
            buffered_segments.append((s, b_start, b_end))

    total_duration = sum(end - start for _, start, end in buffered_segments)
    total_dur_str = _seconds_to_rational(total_duration, frame_rate)

    sequence = ET.SubElement(project, "sequence", {
        "format": "r1",
        "duration": total_dur_str,
        "tcStart": "0/1s",
        "tcFormat": "DF" if abs(frame_rate - 29.97) < 0.01 else "NDF",
    })

    spine = ET.SubElement(sequence, "spine")

    # ── Clips ──
    record_pos = 0.0
    for seg, b_start, b_end in buffered_segments:
        duration = b_end - b_start

        offset_str = _seconds_to_rational(record_pos, frame_rate)
        start_str = _seconds_to_rational(b_start, frame_rate)
        dur_str = _seconds_to_rational(duration, frame_rate)

        clip = ET.SubElement(spine, "asset-clip", {
            "ref": "r2",
            "offset": offset_str,
            "name": f"Segment {seg.script_index}",
            "start": start_str,
            "duration": dur_str,
        })

        # Add note for reordered segments
        if seg.is_reordered:
            note = ET.SubElement(clip, "note")
            note.text = f"REORDERED from position {seg.original_position}"

        record_pos += duration

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
