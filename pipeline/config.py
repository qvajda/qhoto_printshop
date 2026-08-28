import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_STATIC_CONFIG_PATH = REPO_ROOT / "config" / "static_config.json"


class MissingConfigError(Exception):
    pass


def parse_env_file(path) -> dict:
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_env(env_path=None) -> None:
    env_path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    if not env_path.exists():
        return
    for key, value in parse_env_file(env_path).items():
        os.environ.setdefault(key, value)


def require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise MissingConfigError(f"Missing required environment variable: {key}")
    return value


def load_static_config(path=None) -> dict:
    path = Path(path) if path else DEFAULT_STATIC_CONFIG_PATH
    return json.loads(Path(path).read_text())


def is_placeholder(template_id: str) -> bool:
    return template_id.startswith("PLACEHOLDER_")


def get_template_id(static_config: dict, size: str, orientation: str) -> str:
    key = f"{size}_{orientation}"
    return static_config["gelato_templates"][key]["template_id"]


def get_template_variant(static_config: dict, size: str, orientation: str) -> dict:
    key = f"{size}_{orientation}"
    return static_config["gelato_templates"][key]


def get_group_type_for_size(static_config: dict, size: str) -> str:
    for group_type, sizes in static_config["aspect_ratio_groups"].items():
        if size in sizes:
            return group_type
    raise MissingConfigError(f"No aspect_ratio_group contains size {size!r}")


def get_shipping_profile_id(static_config: dict) -> str:
    """v4.12 [D3]: one listing per candidate, so one shipping profile per candidate -
    "Gelato: Free shipping". The old per-aspect-ratio-group Small/Large split stopped
    applying the moment all six sizes shared a listing (Etsy allows exactly one profile
    per listing)."""
    profile_id = static_config["etsy_shipping_profile_id"]
    if not profile_id:
        raise MissingConfigError("etsy_shipping_profile_id is not set")
    return profile_id


# [D2] How long a secondary group may sit undecided before the candidate stops waiting
# and publishes without it (marking that group 'stalled_skipped'). Deliberately long:
# a size aged out of a published listing cannot be added back (GL-22a Q2), while a
# design left unpublished is recoverable by tapping a button. Only fires once GL-7
# evaluates the publish gate on a cadence - test it by lowering this, never by waiting.
GROUP_REVIEW_STALL_DAYS = 14

# GL-31: the deferred half of [D2] - re-send a still-open secondary group's digest
# entry once, this many days before it ages out, so the only signal isn't the owner
# remembering an untapped entry. Must stay below GROUP_REVIEW_STALL_DAYS or the ping
# would never fire before the group is already skipped.
GROUP_REVIEW_REMINDER_DAYS = 10
assert GROUP_REVIEW_REMINDER_DAYS < GROUP_REVIEW_STALL_DAYS


def get_mockup_templates(static_config: dict, group_type: str, orientation: str) -> list[str]:
    """Ordered scene IDs for (group_type, orientation). Resolved once from
    static config; never discovered at runtime (same rule as the Gelato
    template IDs)."""
    return static_config["mockup_templates"][group_type][orientation]


def mockup_bundle_dir(group_type: str, orientation: str, scene_id: str) -> Path:
    """assets/mockups/<group_type>/<orientation>/<scene_id>/ — may not exist on
    disk (the placeholder case); callers pass this straight to
    mockup_render.load_bundle, which raises MockupRenderError if it's
    incomplete/missing. Do not check existence here — that check belongs to
    load_bundle (fail loud), not this resolver."""
    return REPO_ROOT / "assets" / "mockups" / group_type / orientation / scene_id


def is_live_mode(service: str) -> bool:
    return os.environ.get(f"{service}_LIVE_MODE", "").strip().lower() == "true"


# GL-61 operability knobs. Every default reproduces today's behaviour exactly, so an
# unconfigured .env is not a behaviour change. Resolved through here and nowhere else
# (the static-config rule: read once, never discovered at runtime).
RESEARCH_MODES = ("always", "consume-pending-only", "if-nothing-pending")


def research_mode() -> str:
    """'always' (default, today's behaviour) · 'consume-pending-only' (never propose new
    candidates - the mode for draining a backlog through GL-56 without piling more on
    top) · 'if-nothing-pending' (propose only when nothing is still in flight)."""
    mode = os.environ.get("RESEARCH_MODE", "").strip().lower() or "always"
    if mode not in RESEARCH_MODES:
        raise MissingConfigError(
            f"RESEARCH_MODE={mode!r} is not one of {', '.join(RESEARCH_MODES)}"
        )
    return mode


def candidates_per_batch() -> int | None:
    """Cap on how many candidates one generate cycle will process. None (the default) is
    uncapped - today's behaviour. Also GL-59's cheap mitigation: fewer generate calls
    per cycle is less queue depth against Replicate's 6/min granted-credit cap."""
    raw = os.environ.get("CANDIDATES_PER_BATCH", "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < 1:
        raise MissingConfigError(f"CANDIDATES_PER_BATCH must be >= 1, got {value}")
    return value


def telegram_error_verbosity() -> str:
    """'full' (default, today's behaviour: the exception text goes to Telegram) or
    'brief' (stage name only - the exception still goes to the log)."""
    return os.environ.get("TELEGRAM_ERROR_VERBOSITY", "").strip().lower() or "full"


R2_ENV_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_ENDPOINT",
    "R2_PUBLIC_BASE_URL",
)


def is_r2_configured() -> bool:
    return all(os.environ.get(key) for key in R2_ENV_VARS)
