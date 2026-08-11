"""GL-62: the scheduled tasks captured no output at all, so diagnosing a run meant
guessing from CPU time and DB polling. A file handler here rather than a redirect in
the Task Scheduler action: it travels with the repo, it is testable, and it survives
the host move GL-3's VPS fork makes non-hypothetical.

Nothing credential-shaped may reach a log line - TELEGRAM_ADMIN_CHAT_ID is treated as
a credential (CLAUDE.md), and it appears in ordinary stage output, so `redact` scrubs
it and the bot token before writing.
"""
import os
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
MAX_BYTES = 5 * 1024 * 1024  # one rotation kept -> 10 MB ceiling on the owner's disk

_SECRET_ENV_VARS = (
    "TELEGRAM_ADMIN_CHAT_ID",
    "TELEGRAM_BOT_TOKEN",
    "REPLICATE_API_TOKEN",
    "ANTHROPIC_API_KEY",
    "GELATO_API_KEY",
    "ETSY_API_KEY",
    "ETSY_API_SECRET",
    "ETSY_ACCESS_TOKEN",
)


def redact(text: str) -> str:
    for key in _SECRET_ENV_VARS:
        value = os.environ.get(key)
        # 6 is short enough to keep the chat id (a 9-10 digit number) in scope and long
        # enough that an empty/one-char env var cannot blank out the whole log.
        if value and len(value) >= 6:
            text = text.replace(value, f"<{key}>")
    return text


class _LogFile:
    """The one open handle stdout and stderr share, so they interleave in order and
    rotate together. ponytail: size-based rotation with one backup kept; switch to
    logging.handlers if the log ever needs levels or multiple sinks."""

    def __init__(self, path):
        self._path = Path(path)
        self._handle = open(self._path, "a", encoding="utf-8", errors="replace")

    def write(self, text):
        self._handle.write(redact(text))
        self._handle.flush()
        if self._handle.tell() > MAX_BYTES:
            self._handle.close()
            backup = self._path.with_name(self._path.name + ".1")
            backup.unlink(missing_ok=True)
            self._path.replace(backup)
            self._handle = open(self._path, "a", encoding="utf-8", errors="replace")

    def close(self):
        self._handle.close()

    def flush(self):
        self._handle.flush()


class _Tee:
    """Writes through to the original stream and to the shared log file. Deliberately
    not `logging` - every stage already prints, and rewriting them all into a logger is
    a much larger change than the problem asks for."""

    def __init__(self, stream, log_file):
        self._stream = stream
        self._log = log_file

    def write(self, text):
        self._stream.write(text)
        self._log.write(text)
        return len(text)

    def flush(self):
        self._stream.flush()
        self._log.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def start(job_name: str, log_dir=None):
    """Tee stdout+stderr into logs/<job_name>.log. Returns a zero-arg stop callable."""
    log_dir = Path(log_dir) if log_dir else LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = _LogFile(log_dir / f"{job_name}.log")
    saved = (sys.stdout, sys.stderr)
    sys.stdout, sys.stderr = _Tee(saved[0], log_file), _Tee(saved[1], log_file)

    def stop():
        sys.stdout, sys.stderr = saved
        log_file.close()

    return stop
