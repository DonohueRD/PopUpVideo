import os
import sys
import subprocess
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("INTEGRATION"),
    reason="set INTEGRATION=1 to run full pipeline",
)


def test_full_pipeline_dry_run():
    """Run the full pipeline on a short known-good video with --dry-run."""
    url = os.environ.get("TEST_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    result = subprocess.run(
        [sys.executable, "/DATA/docker/tunarr/popup-video/popupvideo.py",
         "-u", url,
         "--no-rescan",
         "--dry-run"],
        capture_output=True, text=True, timeout=120,
        cwd="/DATA/docker/tunarr/popup-video",
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}\nSTDOUT: {result.stdout}"
    assert "Generating factoids" in result.stdout
    assert "[dry-run]" in result.stdout
