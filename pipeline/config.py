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


def get_shipping_profile_id(static_config: dict, group_type: str) -> str:
    profile_id = static_config["etsy_shipping_profile_id"][group_type]
    if not profile_id:
        raise MissingConfigError(
            f"etsy_shipping_profile_id for group {group_type!r} is not set"
        )
    return profile_id


def is_live_mode(service: str) -> bool:
    return os.environ.get(f"{service}_LIVE_MODE") == "true"
