#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
from pathlib import Path

PACK_DIR = Path('datasets/packs')
COMPILED_DIR = Path('datasets/compiled')


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main() -> None:
    pack_paths = sorted(PACK_DIR.glob('*.jsonl'))
    rows: list[dict] = []
    for path in pack_paths:
        rows.extend(read_jsonl(path))

    ids: set[str] = set()
    duplicate_ids: list[str] = []
    families: dict[str, list[dict]] = collections.defaultdict(list)
    prompt_keys: collections.Counter = collections.Counter()
    narrative_answers: collections.Counter = collections.Counter()
    director_types: collections.Counter = collections.Counter()

    for row in rows:
        rid = row['id']
        if rid in ids:
            duplicate_ids.append(rid)
        ids.add(rid)
        families[row['family']].append(row)
        if row['kind'] == 'DIRECTOR':
            key = (
                row.get('mode'),
                row.get('current_scene', ''),
                row.get('player_action', ''),
                json.dumps(row.get('check', {}), ensure_ascii=False, sort_keys=True),
                json.dumps(row.get('state', {}), ensure_ascii=False, sort_keys=True),
            )
            director_types[(row.get('split'), row.get('mode'), row['target']['type'])] += 1
        else:
            key = tuple(m['content'] for m in row['messages'][:-1])
            narrative_answers[row['messages'][-1]['content'].strip()] += 1
        prompt_keys[key] += 1

    leakage = [family for family, vals in families.items() if len({v['split'] for v in vals}) > 1]
    exact_prompt_dupes = sum(count - 1 for count in prompt_keys.values() if count > 1)
    narrative_duplicate_answers = sum(count - 1 for count in narrative_answers.values() if count > 1)
    narrative_total = sum(1 for row in rows if row['kind'] == 'NARRATIVE')
    narrative_unique_rate = len(narrative_answers) / max(1, narrative_total)

    print('Dataset audit')
    print('=============')
    print('Packs:')
    for path in pack_paths:
        print(f'  {path}: {len(read_jsonl(path))}')
    print('Rows:', len(rows))
    print('Kinds:', dict(collections.Counter(r['kind'] for r in rows)))
    print('Splits:', dict(collections.Counter(r['split'] for r in rows)))
    print('Families:', len(families))
    print('Duplicate IDs:', len(duplicate_ids))
    print('Family leakage:', len(leakage))
    print('Exact duplicate prompts:', exact_prompt_dupes)
    print('Narrative unique-answer rate:', f'{narrative_unique_rate:.1%}')
    print('Narrative duplicate answers:', narrative_duplicate_answers)
    print('\nDirector distribution:')
    for key, count in sorted(director_types.items()):
        print(f'  {key[0]:5s} {key[1]:13s} {key[2]:16s} {count:4d}')

    compiled_train = COMPILED_DIR / 'train.jsonl'
    compiled_director = COMPILED_DIR / 'director_eval.jsonl'
    compiled_narrative = COMPILED_DIR / 'narrative_eval.jsonl'
    for path in (compiled_train, compiled_director, compiled_narrative):
        if not path.is_file():
            raise SystemExit(f'AUDIT FAILED: compiled file missing: {path}')

    compiled_rows = read_jsonl(compiled_train) + read_jsonl(compiled_director) + read_jsonl(compiled_narrative)
    marker_errors = 0
    for row in compiled_rows:
        system = row['messages'][0]['content']
        required = '<MODE_DIRECTOR>' if row['kind'] == 'DIRECTOR' else '<MODE_NARRATOR>'
        if not system.startswith(required):
            marker_errors += 1
    print('Mode marker errors:', marker_errors)

    if duplicate_ids or leakage or marker_errors:
        raise SystemExit('AUDIT FAILED')
    if narrative_unique_rate < 0.70:
        raise SystemExit('AUDIT FAILED: narrative answers are too repetitive')
    print('AUDIT OK')


if __name__ == '__main__':
    main()
