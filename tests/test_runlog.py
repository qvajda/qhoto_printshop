import sys

import pipeline.runlog as runlog


def test_start_tees_stdout_and_stderr_into_one_log_file(tmp_path, capsys):
    stop = runlog.start("batch", log_dir=tmp_path)
    try:
        print("stage research ok")
        print("stage generate failed", file=sys.stderr)
    finally:
        stop()

    log = (tmp_path / "batch.log").read_text(encoding="utf-8")
    assert "stage research ok" in log
    assert "stage generate failed" in log
    # The console still sees everything - the log is a copy, not a diversion.
    assert "stage research ok" in capsys.readouterr().out


def test_secrets_never_reach_the_log(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "123456789")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "8123:AAH-secret-token")
    stop = runlog.start("hourly", log_dir=tmp_path)
    try:
        print("sendMessage to 123456789 with 8123:AAH-secret-token")
    finally:
        stop()

    log = (tmp_path / "hourly.log").read_text(encoding="utf-8")
    assert "123456789" not in log
    assert "AAH-secret-token" not in log
    assert "<TELEGRAM_ADMIN_CHAT_ID>" in log and "<TELEGRAM_BOT_TOKEN>" in log


def test_log_is_size_bounded_and_keeps_one_rotation(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "MAX_BYTES", 200)
    stop = runlog.start("batch", log_dir=tmp_path)
    try:
        for i in range(40):
            print(f"line {i} " + "x" * 40)
    finally:
        stop()

    assert (tmp_path / "batch.log").stat().st_size <= 200 + 64
    assert (tmp_path / "batch.log.1").exists()
    # One backup only - the ceiling is 2x MAX_BYTES, not unbounded.
    assert not (tmp_path / "batch.log.1.1").exists()
