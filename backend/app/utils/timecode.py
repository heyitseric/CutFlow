import math
from fractions import Fraction


def seconds_to_timecode(seconds: float, frame_rate: float = 29.97) -> str:
    """Convert seconds to timecode format HH:MM:SS:FF for EDL."""
    if seconds < 0:
        seconds = 0.0

    total_frames = round(seconds * frame_rate)
    fps = round(frame_rate)

    frames = total_frames % fps
    total_seconds = total_frames // fps
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60

    return f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}:{int(frames):02d}"


def seconds_to_rational_time(seconds: float, frame_rate: float = 29.97) -> str:
    """
    Convert seconds to Apple rational time format for FCPXML.
    e.g., for 29.97fps: "1001/30000s" per frame
    Returns format like "30030/30000s" for 1.001 seconds at 29.97fps.
    """
    if seconds <= 0:
        return "0/1s"

    # Use Fraction for exact arithmetic
    # 29.97fps = 30000/1001 frames per second
    # So 1 frame = 1001/30000 seconds
    if abs(frame_rate - 29.97) < 0.01:
        timebase = Fraction(30000)
        frame_duration = Fraction(1001)
    elif abs(frame_rate - 23.976) < 0.01:
        timebase = Fraction(24000)
        frame_duration = Fraction(1001)
    elif abs(frame_rate - 59.94) < 0.01:
        timebase = Fraction(60000)
        frame_duration = Fraction(1001)
    else:
        # Integer frame rates
        fps = round(frame_rate)
        timebase = Fraction(fps)
        frame_duration = Fraction(1)

    # Convert seconds to rational time
    sec_frac = Fraction(seconds).limit_denominator(100000)
    total_units = sec_frac * timebase / frame_duration
    total_frames = round(float(total_units))
    numerator = total_frames * int(frame_duration)

    return f"{numerator}/{int(timebase)}s"


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))

    if millis >= 1000:
        millis = 999

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def rational_time_to_seconds(rational: str, frame_rate: float = 29.97) -> float:
    """Parse Apple rational time string back to seconds."""
    # Format: "numerator/denominators"
    if not rational or rational == "0/1s":
        return 0.0

    rational = rational.rstrip("s")
    if "/" in rational:
        num, den = rational.split("/")
        return float(Fraction(int(num), int(den)))
    else:
        return float(rational)
