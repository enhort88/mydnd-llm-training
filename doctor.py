#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

import torch

from training.config import load_config, project_path, resolve_model


def version(name: str) -> str:
    try:
        module = importlib.import_module(name)
        return str(getattr(module, '__version__', 'OK'))
    except Exception as exc:
        return f'NOT READY ({exc})'


def main() -> None:
    config = load_config()
    model = resolve_model(config)
    print('Python:', sys.version.replace('\n', ' '))
    print('nvidia-smi:', shutil.which('nvidia-smi'))
    print('PyTorch:', torch.__version__)
    print('CUDA available:', torch.cuda.is_available())
    print('CUDA runtime:', torch.version.cuda)
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        print('GPU:', torch.cuda.get_device_name(0))
        print('VRAM:', round(props.total_memory / 1024**3, 1), 'GiB')
    for package in ('unsloth', 'transformers', 'trl', 'datasets', 'peft', 'bitsandbytes'):
        print(f'{package}:', version(package))
    print('Resolved model:', model)
    local_dir = project_path(config['local_model_dir'])
    print('Stable local model present:', (local_dir / 'config.json').is_file())
    manifest = project_path('datasets/compiled/manifest.json')
    if manifest.is_file():
        print('Compiled dataset:', json.loads(manifest.read_text(encoding='utf-8')))
    else:
        print('Compiled dataset: NOT READY (run ./mydnd.sh prepare)')


if __name__ == '__main__':
    main()
