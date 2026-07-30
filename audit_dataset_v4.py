#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
from pathlib import Path

from training.contract_v4 import ALLOWED_TYPES

PACK_DIR = Path('datasets/packs')
COMPILED_DIR = Path('datasets/compiled_v4')


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]


def input_lengths(rows: list[dict]) -> tuple[list[int], list[int], list[int]]:
    systems, users, totals = [], [], []
    for row in rows:
        messages = row['messages']
        system = str(messages[0]['content'])
        user = str(messages[1]['content'])
        systems.append(len(system))
        users.append(len(user))
        totals.append(len(system) + len(user))
    return systems, users, totals


def main() -> None:
    pack_paths = sorted(PACK_DIR.glob('*.jsonl'))
    raw = [row for path in pack_paths for row in read_jsonl(path)]
    train_path = COMPILED_DIR / 'train.jsonl'
    director_path = COMPILED_DIR / 'director_eval.jsonl'
    narrative_path = COMPILED_DIR / 'narrative_eval.jsonl'
    for path in (train_path, director_path, narrative_path):
        if not path.is_file():
            raise SystemExit(f'AUDIT FAILED: missing {path}; run python prepare_dataset_v4.py')
    compiled = read_jsonl(train_path) + read_jsonl(director_path) + read_jsonl(narrative_path)

    ids = [str(r.get('id', '')) for r in raw]
    duplicate_ids = len(ids) - len(set(ids))
    families: dict[str, set[str]] = collections.defaultdict(set)
    for row in raw:
        families[str(row.get('family', ''))].add(str(row.get('split', '')))
    leakage = [name for name, splits in families.items() if len(splits) > 1]

    prompt_keys = collections.Counter()
    narrative_answers = collections.Counter()
    train_types = collections.Counter()
    eval_types = collections.Counter()
    marker_errors = 0
    version_errors = 0
    for row in compiled:
        key = tuple(str(m.get('content', '')) for m in row['messages'][:-1])
        prompt_keys[key] += 1
        system = str(row['messages'][0]['content'])
        required = '<MODE_DIRECTOR>' if row['kind'] == 'DIRECTOR' else '<MODE_NARRATOR>'
        marker_errors += int(not system.startswith(required))
        version_errors += int(row.get('prompt_version') != 'v4-compact')
        if row['kind'] == 'NARRATIVE':
            narrative_answers[str(row['messages'][-1]['content']).strip()] += 1

    # Count action coverage directly from the split files.
    for row in read_jsonl(train_path):
        if row['kind'] == 'DIRECTOR':
            train_types[row['expected']['type']] += 1
    for row in read_jsonl(director_path):
        eval_types[row['expected']['type']] += 1

    narrative_total = sum(1 for r in compiled if r['kind'] == 'NARRATIVE')
    narrative_unique_rate = len(narrative_answers) / max(1, narrative_total)
    exact_dupes = sum(count - 1 for count in prompt_keys.values() if count > 1)
    exact_dupe_rate = exact_dupes / max(1, len(compiled))
    systems, users, totals = input_lengths(compiled)

    print('v4 compact dataset audit')
    print('========================')
    print('Rows:', len(raw))
    print('Compiled:', len(compiled))
    print('Families:', len(families))
    print('Duplicate IDs:', duplicate_ids)
    print('Family leakage:', len(leakage))
    print('Mode marker errors:', marker_errors)
    print('Prompt version errors:', version_errors)
    print('Exact duplicate input prompts:', exact_dupes, f'({exact_dupe_rate:.2%})')
    print('Narrative unique-answer rate:', f'{narrative_unique_rate:.1%}')
    print('Input chars system p50/p95/max:', percentile(systems, .50), percentile(systems, .95), max(systems, default=0))
    print('Input chars user   p50/p95/max:', percentile(users, .50), percentile(users, .95), max(users, default=0))
    print('Input chars total  p50/p95/max:', percentile(totals, .50), percentile(totals, .95), max(totals, default=0))

    missing_train = sorted(ALLOWED_TYPES - set(train_types))
    missing_eval = sorted(ALLOWED_TYPES - set(eval_types))
    print('Missing train action types:', missing_train or 'NONE')
    print('Missing eval action types:', missing_eval or 'NONE')

    old_train = Path('datasets/compiled/train.jsonl')
    if old_train.is_file():
        old_rows = read_jsonl(old_train)
        _, _, old_totals = input_lengths(old_rows)
        old_p50 = percentile(old_totals, .50)
        new_p50 = percentile(totals, .50)
        reduction = 1 - new_p50 / max(1, old_p50)
        print('Old v3 input chars p50:', old_p50)
        print('v4 compact reduction p50:', f'{reduction:.1%}')

    failures = []
    if duplicate_ids:
        failures.append('duplicate ids')
    if leakage:
        failures.append('family leakage')
    if marker_errors or version_errors:
        failures.append('prompt markers/version')
    if narrative_unique_rate < 0.95:
        failures.append('narrative uniqueness below 95%')
    if exact_dupe_rate > 0.03:
        failures.append('exact prompt duplicates above 3%')
    if missing_train or missing_eval:
        failures.append('action coverage')
    if failures:
        raise SystemExit('AUDIT FAILED: ' + ', '.join(failures))
    print('AUDIT OK')


if __name__ == '__main__':
    main()
