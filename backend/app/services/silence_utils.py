"""
Silence detection utilities based on ffmpeg silencedetect.

Provides functions to:
1. Detect silence regions in a given time range of an audio file
2. Find precise speech start/end points near a given timestamp
3. Split a clip at internal silence gaps

Reference: video-rough-cut v3 skill's silence_utils.py
"""
import logging
import re
import subprocess

logger = logging.getLogger(__name__)


def detect_silence(
    audio_path: str,
    start_time: float,
    end_time: float,
    noise_db: float = -35,
    min_duration: float = 0.05,
) -> list[dict]:
    """Detect silence regions in a specific time range of an audio file.

    Returns list of dicts with 'start', 'end', 'duration' for each silence
    region. Times are absolute (relative to the original audio file).
    """
    duration = end_time - start_time
    if duration <= 0:
        return []

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", audio_path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("ffmpeg silencedetect failed: %s", e)
        return []

    stderr = result.stderr
    silence_regions = []
    current_start = None

    for line in stderr.split("\n"):
        start_match = re.search(r"silence_start:\s*([\d.]+)", line)
        end_match = re.search(
            r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", line
        )

        if start_match:
            current_start = float(start_match.group(1)) + start_time
        elif end_match:
            silence_end = float(end_match.group(1)) + start_time
            silence_dur = float(end_match.group(2))
            if current_start is not None:
                silence_regions.append({
                    "start": round(current_start, 4),
                    "end": round(silence_end, 4),
                    "duration": round(silence_dur, 4),
                })
            current_start = None

    # Handle silence extending to end (no silence_end logged)
    if current_start is not None:
        silence_regions.append({
            "start": round(current_start, 4),
            "end": round(end_time, 4),
            "duration": round(end_time - current_start, 4),
        })

    return silence_regions


def find_precise_start(
    audio_path: str,
    rough_start: float,
    search_window: float = 0.5,
    noise_db: float = -35,
) -> float:
    """Find precise speech start point near a rough timestamp.

    Searches in [rough_start - window, rough_start + window] for the
    nearest silence-end point (where speech actually begins).
    Falls back to rough_start if no silence found.
    """
    search_start = max(0, rough_start - search_window)
    search_end = rough_start + search_window

    silences = detect_silence(
        audio_path, search_start, search_end,
        noise_db=noise_db, min_duration=0.03,
    )

    if not silences:
        return rough_start

    best_point = rough_start
    best_dist = float("inf")

    for s in silences:
        # End of silence = where speech starts
        if s["end"] <= rough_start + 0.1:
            dist = abs(s["end"] - rough_start)
            if dist < best_dist:
                best_dist = dist
                best_point = s["end"]
        # If rough_start falls within silence, speech starts at silence end
        if s["start"] <= rough_start <= s["end"]:
            best_point = s["end"]
            break

    return round(best_point, 4)


def find_precise_end(
    audio_path: str,
    rough_end: float,
    search_window: float = 0.5,
    noise_db: float = -35,
) -> float:
    """Find precise speech end point near a rough timestamp.

    Searches for the nearest silence-start point (where speech actually ends).
    Falls back to rough_end if no silence found.
    """
    search_start = max(0, rough_end - search_window)
    search_end = rough_end + search_window

    silences = detect_silence(
        audio_path, search_start, search_end,
        noise_db=noise_db, min_duration=0.03,
    )

    if not silences:
        return rough_end

    best_point = rough_end
    best_dist = float("inf")

    for s in silences:
        if s["start"] >= rough_end - 0.1:
            dist = abs(s["start"] - rough_end)
            if dist < best_dist:
                best_dist = dist
                best_point = s["start"]
        # If rough_end falls within silence, speech ended at silence start
        if s["start"] <= rough_end <= s["end"]:
            best_point = s["start"]
            break

    return round(best_point, 4)


def split_clip_at_silences(
    audio_path: str,
    clip_start: float,
    clip_end: float,
    min_silence_duration: float = 0.3,
    noise_db: float = -30,
) -> list[tuple[float, float]]:
    """Split a clip at internal silence gaps > min_silence_duration.

    Returns list of (start, end) tuples for sub-clips.
    If no splits needed, returns [(clip_start, clip_end)].
    """
    silences = detect_silence(
        audio_path, clip_start, clip_end,
        noise_db=noise_db, min_duration=min_silence_duration,
    )

    if not silences:
        return [(clip_start, clip_end)]

    # Filter to only internal silences (not at clip edges)
    internal_silences = []
    for s in silences:
        if s["start"] <= clip_start + 0.05 or s["end"] >= clip_end - 0.05:
            continue
        if s["duration"] >= min_silence_duration:
            internal_silences.append(s)

    if not internal_silences:
        return [(clip_start, clip_end)]

    # Split at each internal silence
    sub_clips = []
    current_start = clip_start

    for silence in internal_silences:
        # End current sub-clip slightly after silence start (natural decay)
        sub_end = round(silence["start"] + 0.02, 4)
        if sub_end > current_start + 0.05:
            sub_clips.append((current_start, sub_end))
        # Start next sub-clip slightly before silence end (natural attack)
        current_start = round(silence["end"] - 0.02, 4)

    # Add final sub-clip
    if clip_end > current_start + 0.05:
        sub_clips.append((current_start, clip_end))

    return sub_clips if sub_clips else [(clip_start, clip_end)]
