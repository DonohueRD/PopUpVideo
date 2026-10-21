import os
import tempfile

from popupvideo import resolve_output_path


def test_output_path_basic():
    with tempfile.TemporaryDirectory() as d:
        p = resolve_output_path("Alanis Morissette", "Ironic", d)
        assert p == os.path.join(d, "Alanis Morissette - Ironic (Huey Pop Up Video).mp4")


def test_output_path_deduplicates():
    with tempfile.TemporaryDirectory() as d:
        base = os.path.join(d, "Alanis Morissette - Ironic (Huey Pop Up Video).mp4")
        open(base, "w").close()
        p = resolve_output_path("Alanis Morissette", "Ironic", d)
        assert p == os.path.join(d, "Alanis Morissette - Ironic (Huey Pop Up Video) (2).mp4")


def test_output_path_deduplicates_multiple():
    with tempfile.TemporaryDirectory() as d:
        for suffix in ["", " (2)", " (3)"]:
            name = f"A - B (Huey Pop Up Video){suffix}.mp4"
            open(os.path.join(d, name), "w").close()
        p = resolve_output_path("A", "B", d)
        assert "(4)" in p


def test_output_path_does_not_overwrite():
    with tempfile.TemporaryDirectory() as d:
        base = os.path.join(d, "X - Y (Huey Pop Up Video).mp4")
        open(base, "w").close()
        p = resolve_output_path("X", "Y", d)
        assert p != base


def test_scan_trigger_sends_json_body():
    # Tunarr (Fastify) 400s an empty body sent as application/json
    import json
    from unittest.mock import patch, MagicMock
    from popupvideo import trigger_tunarr_scan
    resp = MagicMock(status=202)
    resp.__enter__.return_value = resp
    with patch("popupvideo.urllib.request.urlopen", return_value=resp) as op:
        assert trigger_tunarr_scan() is True
    json.loads(op.call_args[0][0].data)
