import os
import subprocess
from pathlib import Path

VAAPI_DEVICE = "/dev/dri/renderD128"
FONTS_DIR = str(Path(__file__).parent / "fonts")


def _escape_ass_path(path: str) -> str:
    """Escape a path for use in an ffmpeg filtergraph string."""
    return path.replace("\\", "\\\\").replace(":", "\\:")


def _ass_filter(ass_path: str) -> str:
    """Burn-in filter; fontsdir points libass at the bundled TTFs (the box has no system fonts)."""
    return f"ass='{_escape_ass_path(ass_path)}':fontsdir='{_escape_ass_path(FONTS_DIR)}'"


def build_vaapi_cmd(src: str, ass_path: str, dst: str) -> list[str]:
    """Build the ffmpeg VAAPI hardware-encode command."""
    return [
        "ffmpeg", "-y",
        "-vaapi_device", VAAPI_DEVICE,
        "-i", src,
        "-vf", f"{_ass_filter(ass_path)},format=nv12,hwupload",
        "-c:v", "h264_vaapi",
        "-b:v", "8M",
        "-maxrate", "12M",
        "-c:a", "copy",
        dst,
    ]


def build_qsv_cmd(src: str, ass_path: str, dst: str) -> list[str]:
    """Build the ffmpeg Intel QSV fallback command (used when VAAPI fails)."""
    return [
        "ffmpeg", "-y",
        "-i", src,
        "-vf", f"{_ass_filter(ass_path)},format=nv12",
        "-c:v", "h264_qsv",
        "-b:v", "8M",
        "-maxrate", "12M",
        "-c:a", "copy",
        dst,
    ]


def encode(src: str, ass_path: str, dst: str) -> str:
    """Encode video with ASS subtitles burned in. VAAPI-first, software fallback."""
    vaapi_result = subprocess.run(
        build_vaapi_cmd(src, ass_path, dst),
        capture_output=True,
    )
    if vaapi_result.returncode == 0:
        return dst

    # VAAPI failed — try QSV fallback
    qsv_result = subprocess.run(
        build_qsv_cmd(src, ass_path, dst),
        capture_output=True,
    )
    if qsv_result.returncode == 0:
        return dst

    if os.path.exists(dst):  # don't leave a partial/0-byte file in the library
        os.remove(dst)
    raise RuntimeError(
        f"ffmpeg encode failed (VAAPI and QSV both failed):\n"
        f"{qsv_result.stderr.decode()[:1000]}"
    )
