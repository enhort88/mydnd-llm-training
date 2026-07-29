#!/usr/bin/env python3
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from training.contract import (
    ABILITY_VALUES,
    ALLOWED_TYPES,
    CHECK_TYPES,
    NPC_MEMORY_VALUES,
    NPC_STATUS_VALUES,
    MODE_ALLOWED_TYPES,
    to_messages,
)

PACK_DIR = Path('datasets/packs')
COMPILED_DIR = Path('datasets/compiled')
TRAIN = COMPILED_DIR / 'train.jsonl'
DIRECTOR_EVAL = COMPILED_DIR / 'director_eval.jsonl'
NARRATIVE_EVAL = COMPILED_DIR / 'narrative_eval.jsonl'
MANIFEST = COMPILED_DIR / 'manifest.json'



def split_for(family: str, eval_percent: int = 20) -> str:
    value = int(hashlib.sha1(family.encode('utf-8')).hexdigest()[:8], 16) % 100
    return 'eval' if value < eval_percent else 'train'

def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding='utf-8') as f:
        for line_number, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as error:
                raise ValueError(f'{path}:{line_number}: invalid JSON: {error}') from error
    return rows


def signed_int(value: str) -> bool:
    if not isinstance(value, str) or not value or value[0] not in '+-':
        return False
    try:
        return int(value) != 0
    except ValueError:
        return False


def validate_director(row: dict) -> None:
    rid = row['id']
    mode = row.get('mode')
    if mode not in MODE_ALLOWED_TYPES:
        raise ValueError(f'{rid}: unsupported mode {mode!r}')
    if mode == 'PLAYER_ACTION' and not row.get('player_action', '').strip():
        raise ValueError(f'{rid}: PLAYER_ACTION is empty')
    if mode == 'CHECK_RESULT':
        check = row.get('check') or {}
        if check.get('attribute') not in CHECK_TYPES:
            raise ValueError(f'{rid}: invalid CHECK_RESULT attribute')
        try:
            dc = int(check.get('dc'))
            int(check.get('roll_total'))
        except (TypeError, ValueError) as error:
            raise ValueError(f'{rid}: invalid CHECK_RESULT numbers') from error
        if not 5 <= dc <= 25 or not str(check.get('reason', '')).strip():
            raise ValueError(f'{rid}: invalid CHECK_RESULT reason/DC')
    if not isinstance(row.get('state'), dict):
        raise ValueError(f'{rid}: state must be object')

    target = row.get('target') or {}
    action_type = target.get('type')
    name = str(target.get('name', ''))
    value = str(target.get('value', ''))
    details = str(target.get('details', ''))

    if action_type not in ALLOWED_TYPES:
        raise ValueError(f'{rid}: unsupported type {action_type!r}')
    if action_type not in MODE_ALLOWED_TYPES[mode]:
        raise ValueError(f'{rid}: {action_type} forbidden in {mode}')
    if len(name) > 120 or len(value) > 80 or len(details) > 300:
        raise ValueError(f'{rid}: field exceeds Java limits')
    if action_type == 'DONE' and any((name, value, details)):
        raise ValueError(f'{rid}: DONE fields must be empty')
    if action_type == 'CHECK':
        try:
            dc = int(value)
        except ValueError as error:
            raise ValueError(f'{rid}: invalid CHECK DC') from error
        if name not in CHECK_TYPES or not 5 <= dc <= 25 or not details:
            raise ValueError(f'{rid}: invalid CHECK')
    if action_type in {'HP', 'MONEY'}:
        if action_type == 'MONEY' and name.upper() != 'PLAYER':
            raise ValueError(f'{rid}: MONEY target must be PLAYER')
        if not name or not signed_int(value) or not details:
            raise ValueError(f'{rid}: invalid {action_type}')
    if action_type == 'NPC_MEMORY' and (not name or value not in NPC_MEMORY_VALUES or not details):
        raise ValueError(f'{rid}: invalid NPC_MEMORY')
    if action_type == 'NPC_STATUS' and (not name or value not in NPC_STATUS_VALUES):
        raise ValueError(f'{rid}: invalid NPC_STATUS')
    if action_type in {'ABILITY_ADD', 'ABILITY_UPDATE'} and (not name or value not in ABILITY_VALUES):
        raise ValueError(f'{rid}: invalid ability')
    if action_type in {'WORLD_ADD', 'WORLD_UPDATE'} and value and value not in {'1', '2', '3'}:
        raise ValueError(f'{rid}: invalid world importance')
    if action_type in {'WORLD_UPDATE', 'QUEST_UPDATE'} and not details:
        raise ValueError(f'{rid}: details required')

    empty_value_types = {
        'INV_ADD', 'INV_REMOVE', 'NPC_UPSERT', 'WORLD_RESOLVE',
        'QUEST_START', 'QUEST_UPDATE', 'QUEST_COMPLETE', 'QUEST_FAIL',
        'ABILITY_REMOVE', 'EFFECT_ADD', 'EFFECT_REMOVE', 'LOCATION',
    }
    if action_type in empty_value_types and value:
        raise ValueError(f'{rid}: value must be empty for {action_type}')
    name_required = ALLOWED_TYPES - {'DONE', 'CHECK', 'HP', 'MONEY'}
    if action_type in name_required and not name:
        raise ValueError(f'{rid}: name required for {action_type}')


def validate_narrative(row: dict) -> None:
    rid = row['id']
    messages = row.get('messages')
    if not isinstance(messages, list) or len(messages) < 3:
        raise ValueError(f'{rid}: narrative messages missing')
    if [m.get('role') for m in messages[-3:]] != ['system', 'user', 'assistant']:
        raise ValueError(f'{rid}: expected system/user/assistant')
    answer = str(messages[-1].get('content', '')).strip()
    if not 40 <= len(answer) <= 700:
        raise ValueError(f'{rid}: narrative length outside 40..700')
    forbidden = ('<|tool_call>', 'director_action{', '```json', '"type":')
    if any(x in answer for x in forbidden):
        raise ValueError(f'{rid}: narrative leaks tool syntax')


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def materialize(row: dict) -> dict:
    if row['kind'] == 'DIRECTOR':
        return {
            'id': row['id'],
            'kind': 'DIRECTOR',
            'family': row['family'],
            'mode': row['mode'],
            'expected': row['target'],
            'messages': to_messages(row),
        }
    messages = [dict(m) for m in row['messages']]
    system = str(messages[0].get('content', '')).strip()
    if not system.startswith('<MODE_NARRATOR>'):
        messages[0]['content'] = '<MODE_NARRATOR>\n' + system
    return {
        'id': row['id'],
        'kind': 'NARRATIVE',
        'family': row['family'],
        'mode': 'NARRATIVE',
        'expected': row.get('expected', {'kind': 'NARRATIVE'}),
        'messages': messages,
    }


def main():
    pack_paths = sorted(PACK_DIR.glob('*.jsonl'))
    if not pack_paths:
        raise SystemExit(f'No dataset packs found in {PACK_DIR}')
    rows = []
    pack_counts = {}
    for pack_path in pack_paths:
        pack_rows = read_jsonl(pack_path)
        rows.extend(pack_rows)
        pack_counts[str(pack_path)] = len(pack_rows)
    seen_ids = set()
    family_splits: dict[str, str] = {}
    for row in rows:
        rid = row.get('id', '')
        if not rid or rid in seen_ids:
            raise ValueError(f'duplicate/empty id: {rid!r}')
        seen_ids.add(rid)
        kind = row.get('kind')
        family = row.get('family')
        split = row.get('split')
        if family and split in {None, '', 'auto'}:
            split = split_for(family)
            row['split'] = split
        if kind not in {'DIRECTOR', 'NARRATIVE'}:
            raise ValueError(f'{rid}: invalid kind {kind!r}')
        if split not in {'train', 'eval'} or not family:
            raise ValueError(f'{rid}: split/family missing')
        if family in family_splits and family_splits[family] != split:
            raise ValueError(f'{rid}: family leakage for {family}')
        family_splits[family] = split
        if kind == 'DIRECTOR':
            validate_director(row)
        else:
            validate_narrative(row)

    train = [materialize(r) for r in rows if r['split'] == 'train']
    director_eval = [materialize(r) for r in rows if r['split'] == 'eval' and r['kind'] == 'DIRECTOR']
    narrative_eval = [materialize(r) for r in rows if r['split'] == 'eval' and r['kind'] == 'NARRATIVE']

    write_jsonl(TRAIN, train)
    write_jsonl(DIRECTOR_EVAL, director_eval)
    write_jsonl(NARRATIVE_EVAL, narrative_eval)

    manifest = {
        'packs': pack_counts,
        'total_rows': len(rows),
        'train_rows': len(train),
        'director_eval_rows': len(director_eval),
        'narrative_eval_rows': len(narrative_eval),
        'families': len(family_splits),
        'mode_markers': {'director': '<MODE_DIRECTOR>', 'narrator': '<MODE_NARRATOR>'},
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    counts = collections.Counter()
    for row in rows:
        if row['kind'] == 'DIRECTOR':
            counts[(row['split'], row['mode'], row['target']['type'])] += 1
        else:
            counts[(row['split'], 'NARRATIVE', 'TEXT')] += 1

    print('Dataset packs:')
    for name, count in pack_counts.items():
        print(f'  {name}: {count}')
    print(f'Validated:      {len(rows)}')
    print(f'Train mixed:   {len(train)}')
    print(f'Director eval: {len(director_eval)}')
    print(f'Narrative eval:{len(narrative_eval)}')
    print(f'Families:       {len(family_splits)} (zero family leakage)')
    print('\nDistribution:')
    for (split, mode, action), count in sorted(counts.items()):
        print(f'  {split:5s} {mode:13s} {action:16s} {count:4d}')


if __name__ == '__main__':
    main()
