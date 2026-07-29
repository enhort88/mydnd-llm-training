from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path = 'config/default.json') -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    data = json.loads(config_path.read_text(encoding='utf-8'))
    data['_config_path'] = str(config_path)
    return data


def project_path(value: str | Path) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(str(value))))
    return p if p.is_absolute() else ROOT / p


def resolve_model(config: dict[str, Any], explicit: str | None = None) -> str:
    if explicit:
        return os.path.expandvars(os.path.expanduser(explicit))
    env_model = os.environ.get('MYDND_BASE_MODEL')
    if env_model:
        return os.path.expandvars(os.path.expanduser(env_model))
    local_dir = project_path(config['local_model_dir'])
    if (local_dir / 'config.json').is_file():
        return str(local_dir)
    return str(config['base_model'])
