import subprocess
from unittest.mock import patch

from encoder import build_vaapi_cmd, build_qsv_cmd, encode


def test_vaapi_cmd_structure():
    cmd = build_vaapi_cmd("/src/video.mp4", "/tmp/subs.ass", "/out/video.mp4")
    joined = " ".join(cmd)
    assert "-vaapi_device" in joined
    assert "/dev/dri/renderD128" in joined
    assert "h264_vaapi" in joined
    assert "subs.ass" in joined
    assert "-c:a" in joined
    assert "copy" in joined


def test_vaapi_cmd_ass_before_hwupload():
    cmd = build_vaapi_cmd("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
    vf = next(cmd[i + 1] for i, c in enumerate(cmd) if c == "-vf")
    assert vf.index("ass=") < vf.index("hwupload")


def test_qsv_cmd_structure():
    cmd = build_qsv_cmd("/src/video.mp4", "/tmp/subs.ass", "/out/video.mp4")
    joined = " ".join(cmd)
    assert "h264_qsv" in joined
    assert "subs.ass" in joined
    assert "-c:a" in joined
    assert "copy" in joined


def test_vaapi_cmd_includes_output_path():
    cmd = build_vaapi_cmd("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
    assert cmd[-1] == "/out/v.mp4"


def test_qsv_cmd_includes_output_path():
    cmd = build_qsv_cmd("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
    assert cmd[-1] == "/out/v.mp4"


def test_encode_falls_back_to_qsv_on_vaapi_failure():
    with patch("encoder.subprocess.run") as mock_run:
        fail = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"VAAPI init failed")
        ok = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        mock_run.side_effect = [fail, ok]
        result = encode("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
        assert result == "/out/v.mp4"
        assert mock_run.call_count == 2
        # second call should use QSV
        qsv_cmd = " ".join(mock_run.call_args_list[1][0][0])
        assert "h264_qsv" in qsv_cmd


def test_encode_returns_dst_on_vaapi_success():
    with patch("encoder.subprocess.run") as mock_run:
        ok = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        mock_run.return_value = ok
        result = encode("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
        assert result == "/out/v.mp4"
        assert mock_run.call_count == 1


def test_encode_raises_if_both_fail():
    import pytest
    with patch("encoder.subprocess.run") as mock_run:
        fail = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"error")
        mock_run.return_value = fail
        with pytest.raises(RuntimeError, match="VAAPI and QSV both failed"):
            encode("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
        assert mock_run.call_count == 2


def test_both_cmds_pass_fontsdir():
    for build in (build_vaapi_cmd, build_qsv_cmd):
        cmd = build("/src/v.mp4", "/tmp/s.ass", "/out/v.mp4")
        vf = next(cmd[i + 1] for i, c in enumerate(cmd) if c == "-vf")
        assert "fontsdir=" in vf
        assert "popup-video/fonts" in vf


def test_encode_removes_partial_output_on_failure(tmp_path):
    import pytest
    dst = tmp_path / "out.mp4"

    def fake_run(cmd, **kw):
        dst.write_bytes(b"")  # ffmpeg leaves a 0-byte file behind
        return subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"error")

    with patch("encoder.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError):
            encode("/src/v.mp4", "/tmp/s.ass", str(dst))
    assert not dst.exists()
