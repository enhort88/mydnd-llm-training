#!/usr/bin/env python3
from __future__ import annotations

import unsloth  # noqa: F401

import argparse
from pathlib import Path

import torch
from unsloth import FastModel, get_chat_template

from training.config import load_config, project_path


def parse_args():
    p = argparse.ArgumentParser(description='Export the trained MyDND adapter to GGUF.')
    p.add_argument('--config', default='config/default.json')
    p.add_argument('--adapter')
    p.add_argument('--output-dir', default='outputs/mydnd-e2b-v3-gguf')
    p.add_argument('--max-seq-length', type=int)
    p.add_argument('--quantization', default='q8_0',
                   help='Start with q8_0. Try q4_k_m after validating the merged model.')
    return p.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)
    args.adapter = str(project_path(args.adapter or cfg['output_dir']))
    args.output_dir = str(project_path(args.output_dir))
    args.max_seq_length = args.max_seq_length or int(cfg['max_seq_length'])
    if not torch.cuda.is_available():
        raise SystemExit('CUDA GPU is required to load and merge the adapter.')
    model, processor = FastModel.from_pretrained(
        model_name=args.adapter,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
        full_finetuning=False,
    )
    processor = get_chat_template(processor, chat_template='gemma-4')
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained_gguf(
        str(output),
        processor,
        quantization_method=args.quantization,
    )
    print(f'GGUF export finished: {output.resolve()}')


if __name__ == '__main__':
    main()
