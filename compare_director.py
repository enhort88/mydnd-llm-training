#!/usr/bin/env python3
from __future__ import annotations

import unsloth  # noqa: F401

import argparse
import collections
import gc
import json
import re
from pathlib import Path

import torch
from datasets import load_dataset
from unsloth import FastModel, get_chat_template

from training.config import load_config, project_path, resolve_model

from training.contract import (
    ABILITY_VALUES,
    ALLOWED_TYPES,
    CHECK_TYPES,
    MODE_ALLOWED_TYPES,
    NPC_MEMORY_VALUES,
    NPC_STATUS_VALUES,
)

CALL_RE = re.compile(r'(?:call\s*:\s*)?director_action\s*\{(.*?)\}', re.I | re.S)
SPECIAL_RE = re.compile(r'([a-zA-Z_]+)\s*:\s*<\|"\|>(.*?)<\|"\|>', re.S)
NORMAL_RE = re.compile(r'([a-zA-Z_]+)\s*:\s*"(.*?)"', re.S)


def parse_args():
    p = argparse.ArgumentParser(description='Compare base Gemma and MyDND LoRA on held-out Director cases.')
    p.add_argument('--config', default='config/default.json')
    p.add_argument('--base-model')
    p.add_argument('--adapter')
    p.add_argument('--eval-file')
    p.add_argument('--limit', type=int, default=0, help='0 = all holdout examples')
    p.add_argument('--max-seq-length', type=int)
    p.add_argument('--max-new-tokens', type=int)
    p.add_argument('--skip-base', action='store_true')
    p.add_argument('--report', default='reports/director-comparison.json')
    return p.parse_args()


def merge_args(args):
    cfg = load_config(args.config)
    args.base_model = resolve_model(cfg, args.base_model)
    args.adapter = str(project_path(args.adapter or cfg['output_dir']))
    args.eval_file = str(project_path(args.eval_file or cfg['director_eval']))
    args.max_seq_length = args.max_seq_length or int(cfg['max_seq_length'])
    args.max_new_tokens = args.max_new_tokens or int(cfg['max_new_tokens_director'])
    if args.limit < 0:
        args.limit = 0
    return args


def parse_tool(text: str):
    call = CALL_RE.search(text or '')
    if not call:
        return None
    body = call.group(1)
    fields = {}
    for pattern in (SPECIAL_RE, NORMAL_RE):
        for match in pattern.finditer(body):
            fields.setdefault(match.group(1).lower(), match.group(2).strip())
    if 'type' not in fields:
        return None
    return {k: fields.get(k, '') for k in ('type', 'name', 'value', 'details')}


def signed_delta(value: str, limit: int) -> bool:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    return parsed != 0 and -limit <= parsed <= limit


def java_contract_valid(action: dict | None, mode: str) -> bool:
    if not action:
        return False
    action_type = str(action.get('type', '')).upper()
    name = str(action.get('name', ''))
    value = str(action.get('value', ''))
    details = str(action.get('details', ''))

    if action_type not in ALLOWED_TYPES or action_type not in MODE_ALLOWED_TYPES.get(mode, set()):
        return False
    if len(name) > 120 or len(value) > 80 or len(details) > 300:
        return False
    if action_type == 'DONE':
        return not name and not value and not details
    if action_type == 'CHECK':
        try:
            dc = int(value)
        except ValueError:
            return False
        return name in CHECK_TYPES and 5 <= dc <= 25 and bool(details)
    if action_type == 'HP':
        return bool(name) and signed_delta(value, 1_000) and bool(details)
    if action_type == 'MONEY':
        return name.upper() == 'PLAYER' and signed_delta(value, 1_000_000) and bool(details)
    if action_type == 'NPC_MEMORY':
        return bool(name) and value.upper() in NPC_MEMORY_VALUES and bool(details)
    if action_type == 'NPC_STATUS':
        return bool(name) and value.upper() in NPC_STATUS_VALUES
    if action_type in {'ABILITY_ADD', 'ABILITY_UPDATE'}:
        return bool(name) and value.upper() in ABILITY_VALUES
    if action_type == 'WORLD_ADD':
        return bool(name) and (not value or value in {'1', '2', '3'})
    if action_type == 'WORLD_UPDATE':
        return bool(name) and bool(details) and (not value or value in {'1', '2', '3'})
    if action_type == 'QUEST_UPDATE':
        return bool(name) and not value and bool(details)

    empty_value_types = {
        'INV_ADD', 'INV_REMOVE', 'NPC_UPSERT', 'WORLD_RESOLVE',
        'QUEST_START', 'QUEST_COMPLETE', 'QUEST_FAIL', 'ABILITY_REMOVE',
        'EFFECT_ADD', 'EFFECT_REMOVE', 'LOCATION',
    }
    return bool(name) and (action_type not in empty_value_types or not value)


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


def aggregate(cases: list[dict]) -> dict:
    total = len(cases)
    if total == 0:
        return {'count': 0}
    return {
        'count': total,
        'tool_syntax_rate': sum(x['syntax_ok'] for x in cases) / total,
        'java_contract_valid_rate': sum(x['java_contract_valid'] for x in cases) / total,
        'action_type_accuracy': sum(x['type_ok'] for x in cases) / total,
        'identity_fields_accuracy': sum(x['identity_fields_ok'] for x in cases) / total,
        'all_fields_exact_rate': sum(x['fields_exact'] for x in cases) / total,
    }


def grouped_metrics(cases: list[dict], key: str) -> dict:
    grouped = collections.defaultdict(list)
    for case in cases:
        grouped[str(case[key])].append(case)
    return {name: aggregate(values) for name, values in sorted(grouped.items())}


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

    results = []
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
        predicted = parse_tool(output)
        expected = row['expected']
        mode = row['mode']
        syntax_ok = predicted is not None
        type_ok = syntax_ok and predicted['type'].upper() == expected['type'].upper()
        identity_fields_ok = type_ok and all(
            predicted.get(k, '').strip() == str(expected.get(k, '')).strip()
            for k in ('name', 'value')
        )
        fields_ok = identity_fields_ok and (
            predicted.get('details', '').strip() == str(expected.get('details', '')).strip()
        )
        contract_ok = java_contract_valid(predicted, mode)
        mark = 'OK' if type_ok else 'FAIL'
        got = predicted['type'] if predicted else 'NO_TOOL'
        print(f'[{index:02d}/{len(rows):02d}] {mark:4s} {row["id"]}: expected={expected["type"]}, got={got}')
        results.append({
            'id': row['id'],
            'mode': mode,
            'expected_type': expected['type'],
            'expected': expected,
            'predicted': predicted,
            'syntax_ok': syntax_ok,
            'java_contract_valid': contract_ok,
            'type_ok': type_ok,
            'identity_fields_ok': identity_fields_ok,
            'fields_exact': fields_ok,
            'raw_output': output,
        })

    metrics = aggregate(results)
    metrics['by_mode'] = grouped_metrics(results, 'mode')
    metrics['by_expected_type'] = grouped_metrics(results, 'expected_type')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    del model, processor
    gc.collect()
    torch.cuda.empty_cache()
    return {'model': model_name, 'metrics': metrics, 'cases': results}


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
