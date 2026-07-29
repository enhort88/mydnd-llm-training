#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

from training.config import load_config, project_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Cache the trainable Gemma checkpoint once in a stable local folder.')
    parser.add_argument('--config', default='config/default.json')
    parser.add_argument('--repo-id')
    parser.add_argument('--local-dir')
    args = parser.parse_args()

    config = load_config(args.config)
    repo_id = args.repo_id or config['base_model']
    local_dir = project_path(args.local_dir or config['local_model_dir'])
    local_dir.mkdir(parents=True, exist_ok=True)

    print(f'Repository: {repo_id}')
    print(f'Local model directory: {local_dir}')
    print('Hugging Face will reuse files already present in ~/.cache/huggingface/hub.')
    snapshot_download(repo_id=repo_id, local_dir=str(local_dir))
    print('\nModel is ready. Future training runs use the local directory and do not download it again.')
    print(f'Optional offline mode:\n  export MYDND_BASE_MODEL="{local_dir}"')
    print('  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1')


if __name__ == '__main__':
    main()
