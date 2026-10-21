from downloader import parse_title


def test_dash_format():
    assert parse_title("Alanis Morissette - Ironic (Official 4K)", "AlanisVEVO") == \
        ("Alanis Morissette", "Ironic")


def test_by_format():
    # "Title by Artist" — artist extracted to second position
    artist, song = parse_title("Ironic by Alanis Morissette", "AlanisVEVO")
    assert artist == "Alanis Morissette"


def test_no_separator_falls_back_to_uploader():
    artist, song = parse_title("Ironic (Official Video)", "AlanisVEVO")
    assert artist == "AlanisVEVO"
    assert song == "Ironic (Official Video)"


def test_featuring_in_title():
    artist, song = parse_title("Warren G - Regulate ft. Nate Dogg", "WarrenGVEVO")
    assert artist == "Warren G"
    assert "Regulate" in song


def test_strips_common_suffixes():
    _, song = parse_title("Artist - Song (Official Music Video)", "VEVO")
    assert "Official Music Video" not in song
    assert song == "Song"


def test_strips_hd_suffix():
    _, song = parse_title("Artist - Song (Official HD Video)", "VEVO")
    assert song == "Song"


def test_download_reports_video_size(tmp_path):
    import json, subprocess
    from unittest.mock import patch
    from downloader import download
    info = {"id": "abc", "title": "Paul Wall - Sittin' Sidewayz", "uploader": "x",
            "duration": 200, "width": 1440, "height": 1080}
    done = subprocess.CompletedProcess([], 0, stdout=json.dumps(info).encode(), stderr=b"")
    with patch("downloader.subprocess.run", return_value=done):
        meta = download("https://youtu.be/abc", str(tmp_path))
    assert (meta["width"], meta["height"]) == (1440, 1080)


def test_download_defaults_video_size_when_missing(tmp_path):
    import json, subprocess
    from unittest.mock import patch
    from downloader import download
    info = {"id": "abc", "title": "A - B", "uploader": "x", "duration": 200}
    done = subprocess.CompletedProcess([], 0, stdout=json.dumps(info).encode(), stderr=b"")
    with patch("downloader.subprocess.run", return_value=done):
        meta = download("https://youtu.be/abc", str(tmp_path))
    assert (meta["width"], meta["height"]) == (1920, 1080)


def _run_download(tmp_path, cookies):
    import json, subprocess
    from unittest.mock import patch
    import downloader
    info = {"id": "abc", "title": "A - B", "uploader": "x", "duration": 200}
    done = subprocess.CompletedProcess([], 0, stdout=json.dumps(info).encode(), stderr=b"")
    with patch.object(downloader, "COOKIES_FILE", str(cookies)), \
         patch("downloader.subprocess.run", return_value=done) as run:
        downloader.download("https://youtu.be/abc", str(tmp_path))
    return run.call_args[0][0]


def test_download_uses_cookies_file_when_present(tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    cmd = _run_download(tmp_path, cookies)
    assert cmd[cmd.index("--cookies") + 1] == str(cookies)


def test_download_works_without_cookies_file(tmp_path):
    cmd = _run_download(tmp_path, tmp_path / "missing.txt")
    assert "--cookies" not in cmd
