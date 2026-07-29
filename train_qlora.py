#!/usr/bin/env python3
from __future__ import annotations

# Unsloth must patch libraries before transformers/trl imports.
import unsloth  # noqa: F401

import argparse
import inspect
import json
import platform
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import Trainer as HFTrainer
from trl import SFTConfig, SFTTrainer
from unsloth import FastModel, get_chat_template, is_bfloat16_supported, train_on_responses_only

from training.config import load_config, project_path, resolve_model


def parse_args():
    p = argparse.ArgumentParser(description='Mixed QLoRA fine-tuning for MyDND Director + narrator.')
    p.add_argument('--config', default='config/default.json')
    p.add_argument('--model')
    p.add_argument('--train-file')
    p.add_argument('--output-dir')
    p.add_argument('--max-seq-length', type=int)
    p.add_argument('--max-steps', type=int, default=0, help='When >0 overrides epochs.')
    p.add_argument('--epochs', type=float)
    p.add_argument('--batch-size', type=int)
    p.add_argument('--gradient-accumulation', type=int)
    p.add_argument('--learning-rate', type=float)
    p.add_argument('--lora-r', type=int)
    p.add_argument('--seed', type=int)
    p.add_argument('--save-steps', type=int)
    return p.parse_args()


def merge_args(args):
    cfg = load_config(args.config)
    args.model = resolve_model(cfg, args.model)
    args.train_file = str(project_path(args.train_file or cfg['compiled_train']))
    args.output_dir = str(project_path(args.output_dir or cfg['output_dir']))
    args.max_seq_length = args.max_seq_length or int(cfg['max_seq_length'])
    args.epochs = args.epochs if args.epochs is not None else float(cfg['epochs'])
    args.batch_size = args.batch_size or int(cfg['batch_size'])
    args.gradient_accumulation = args.gradient_accumulation or int(cfg['gradient_accumulation'])
    args.learning_rate = args.learning_rate if args.learning_rate is not None else float(cfg['learning_rate'])
    args.lora_r = args.lora_r or int(cfg['lora_r'])
    args.seed = args.seed or int(cfg['seed'])
    args.save_steps = args.save_steps or int(cfg['save_steps'])
    return args


def require_cuda():
    if not torch.cuda.is_available():
        raise SystemExit('CUDA GPU is required.')
    props = torch.cuda.get_device_properties(0)
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {props.total_memory / 1024**3:.1f} GiB')
    print(f'PyTorch: {torch.__version__}; CUDA runtime: {torch.version.cuda}')


def apply_template(processor, messages, *, generation=False):
    kwargs = dict(tokenize=False, add_generation_prompt=generation)
    try:
        return processor.apply_chat_template(messages, enable_thinking=False, **kwargs)
    except TypeError:
        return processor.apply_chat_template(messages, **kwargs)


def supported_kwargs(callable_obj, values: dict) -> dict:
    try:
        params = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return values
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return values
    return {k: v for k, v in values.items() if k in params}


def main():
    args = merge_args(parse_args())
    require_cuda()
    train_path = Path(args.train_file)
    if not train_path.is_file():
        raise SystemExit(f'{train_path} not found. Run ./mydnd.sh prepare')

    print(f'Loading base model: {args.model}')
    model, processor = FastModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
        full_finetuning=False,
    )
    processor = get_chat_template(processor, chat_template='gemma-4')

    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=False,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=args.lora_r,
        lora_alpha=args.lora_r,
        lora_dropout=0,
        bias='none',
        use_gradient_checkpointing='unsloth',
        random_state=args.seed,
    )

    dataset = load_dataset('json', data_files=str(train_path), split='train')

    def format_batch(batch):
        return {'text': [apply_template(processor, messages) for messages in batch['messages']]}

    dataset = dataset.map(format_batch, batched=True, desc='Applying Gemma 4 chat template')

    config_values = dict(
        output_dir=args.output_dir,
        dataset_text_field='text',
        max_length=args.max_seq_length,
        max_seq_length=args.max_seq_length,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        warmup_steps=10,
        learning_rate=args.learning_rate,
        logging_steps=1,
        optim='adamw_8bit',
        weight_decay=0.01,
        lr_scheduler_type='cosine',
        seed=args.seed,
        save_strategy='steps',
        save_steps=args.save_steps,
        save_total_limit=2,
        report_to='tensorboard',
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        packing=False,
        dataset_num_proc=1,
    )
    if args.max_steps > 0:
        config_values['max_steps'] = args.max_steps
        config_values['num_train_epochs'] = 1
    else:
        config_values['num_train_epochs'] = args.epochs
        config_values['max_steps'] = -1

    training_args = SFTConfig(**supported_kwargs(SFTConfig, config_values))
    trainer = SFTTrainer(**supported_kwargs(SFTTrainer.__init__, dict(
        model=model,
        train_dataset=dataset,
        args=training_args,
        processing_class=processor,
        tokenizer=processor,
    )))

    trainer = train_on_responses_only(
        trainer,
        instruction_part='<|turn>user\n',
        response_part='<|turn>model\n',
    )

    # TRL 0.24 entropy metric is incompatible with lazy Gemma 4 logits in current Unsloth.
    # This disables only auxiliary entropy/token-accuracy metrics; model loss remains intact.
    trainer.compute_loss = HFTrainer.compute_loss.__get__(trainer, trainer.__class__)

    stats = trainer.train()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output)
    processor.save_pretrained(output)

    kind_counts = {}
    for kind in dataset['kind']:
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    metadata = {
        'base_model': args.model,
        'train_file': str(train_path),
        'examples': len(dataset),
        'kind_counts': kind_counts,
        'max_seq_length': args.max_seq_length,
        'max_steps': args.max_steps if args.max_steps > 0 else None,
        'epochs': None if args.max_steps > 0 else args.epochs,
        'learning_rate': args.learning_rate,
        'lora_r': args.lora_r,
        'effective_batch': args.batch_size * args.gradient_accumulation,
        'train_runtime': getattr(stats, 'metrics', {}),
        'platform': platform.platform(),
    }
    (output / 'mydnd_training_metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'\nLoRA adapter saved to: {output.resolve()}')


if __name__ == '__main__':
    main()
