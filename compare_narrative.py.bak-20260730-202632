#!/usr/bin/env python3
from __future__ import annotations

import unsloth  # noqa: F401

import argparse
import gc
import json
import re
from pathlib import Path

import torch
from datasets import load_dataset
from unsloth import FastModel, get_chat_template

from training.config import load_config, project_path, resolve_model

TOOL_MARKERS = ('<|tool_call>', 'director_action{', 'call:director_action', '```json')
CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')
PLAYER_DECISION_PATTERNS = [
    re.compile(r'\bты\s+(?:решаешь|выбираешь|соглашаешься|отказываешься|нападаешь|берёшь|уходишь)\b', re.I),
    re.compile(r'\bгерой\s+(?:решает|выбирает|соглашается|отказывается)\b', re.I),
]


def parse_args():
    p = argparse.ArgumentParser(description='Compare storyteller behavior before/after LoRA.')
    p.add_argument('--config', default='config/default.json')
    p.add_argument('--base-model')
    p.add_argument('--adapter')
    p.add_argument('--eval-file')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--max-seq-length', type=int)
    p.add_argument('--max-new-tokens', type=int)
    p.add_argument('--skip-base', action='store_true')
    p.add_argument('--report', default='reports/narrative-comparison.json')
    return p.parse_args()


def merge_args(args):
    cfg = load_config(args.config)
    args.base_model = resolve_model(cfg, args.base_model)
    args.adapter = str(project_path(args.adapter or cfg['output_dir']))
    args.eval_file = str(project_path(args.eval_file or cfg['narrative_eval']))
    args.max_seq_length = args.max_seq_length or int(cfg['max_seq_length'])
    args.max_new_tokens = args.max_new_tokens or int(cfg['max_new_tokens_narrative'])
    return args


def apply_template(processor, messages):
    kwargs = dict(tokenize=False, add_generation_prompt=True)
    try:
        return processor.apply_chat_template(messages, enable_thinking=False, **kwargs)
    except TypeError:
        return processor.apply_chat_template(messages, **kwargs)


def load_rows(path: str, limit: int):
    rows = list(load_dataset('json', data_files=path, split='train'))
    rows.sort(key=lambda x: x['id'])
    return rows[:limit] if limit > 0 else rows


def evaluate(model_name: str, rows: list[dict], args, label: str):
    print(f'\n=== {label}: {model_name} ===')
    model, processor = FastModel.from_pretrained(
        model_name=model_name,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
        full_finetuning=False,
    )
    processor = get_chat_template(processor, chat_template='gemma-4')
    FastModel.for_inference(model)

    cases = []
    for index, row in enumerate(rows, 1):
        prompt = apply_template(processor, row['messages'][:-1])
        inputs = processor(text=prompt, return_tensors='pt')
        inputs = {k: v.to(model.device) for k, v in inputs.items() if hasattr(v, 'to')}
        input_len = inputs['input_ids'].shape[-1]
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                use_cache=True,
            )
        output = processor.decode(generated[0][input_len:], skip_special_tokens=False).strip()
        visible = output.replace('<turn|>', '').strip()
        letters = [c for c in visible if c.isalpha()]
        cyr = len(CYRILLIC_RE.findall(visible)) / max(1, len(letters))
        tool_leak = any(marker in visible for marker in TOOL_MARKERS)
        agency_violation = any(p.search(visible) for p in PLAYER_DECISION_PATTERNS)
        length_ok = 60 <= len(visible) <= 700
        anchors = list((row.get('expected') or {}).get('anchors') or [])
        anchor_hit = (not anchors) or any(str(anchor).lower() in visible.lower() for anchor in anchors)
        basic_ok = (not tool_leak) and (not agency_violation) and length_ok and cyr >= 0.55
        print(f'[{index:02d}/{len(rows):02d}] {"OK" if basic_ok else "CHECK":5s} {row["id"]}: chars={len(visible)}, tool={tool_leak}, agency={agency_violation}, cyr={cyr:.2f}')
        cases.append({
            'id': row['id'],
            'output': visible,
            'tool_leak': tool_leak,
            'agency_violation': agency_violation,
            'length_ok': length_ok,
            'cyrillic_ratio': cyr,
            'basic_ok': basic_ok,
            'anchors': anchors,
            'anchor_hit': anchor_hit,
        })

    total = max(1, len(cases))
    normalized = [' '.join(c['output'].lower().split()) for c in cases]
    unique_output_rate = len(set(normalized)) / total
    metrics = {
        'count': len(cases),
        'tool_leak_rate': sum(c['tool_leak'] for c in cases) / total,
        'agency_violation_rate': sum(c['agency_violation'] for c in cases) / total,
        'length_ok_rate': sum(c['length_ok'] for c in cases) / total,
        'basic_ok_rate': sum(c['basic_ok'] for c in cases) / total,
        'mean_chars': sum(len(c['output']) for c in cases) / total,
        'mean_cyrillic_ratio': sum(c['cyrillic_ratio'] for c in cases) / total,
        'unique_output_rate': unique_output_rate,
        'anchor_hit_rate': sum(c['anchor_hit'] for c in cases) / total,
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    del model, processor
    gc.collect()
    torch.cuda.empty_cache()
    return {'model': model_name, 'metrics': metrics, 'cases': cases}


def main():
    args = merge_args(parse_args())
    if not torch.cuda.is_available():
        raise SystemExit('CUDA GPU is required.')
    rows = load_rows(args.eval_file, args.limit)
    report = {'eval_file': args.eval_file, 'count': len(rows), 'results': {}}
    if not args.skip_base:
        report['results']['base'] = evaluate(args.base_model, rows, args, 'BASE')
    report['results']['adapter'] = evaluate(args.adapter, rows, args, 'TUNED')
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nReport saved to: {path.resolve()}')


if __name__ == '__main__':
    main()
