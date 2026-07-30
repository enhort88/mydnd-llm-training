#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def pct(value: float | int | None) -> str:
    return f'{100.0 * float(value or 0):.2f}%'


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--director', default='reports/director-v4-fixed.json')
    p.add_argument('--narrative', default='reports/narrative-v4-fixed.json')
    p.add_argument('--summary', default='reports/v4-fixed-summary.txt')
    p.add_argument('--review', default='reports/narrative-v4-fixed-review.md')
    p.add_argument('--zip', dest='zip_path', default='reports/v4-fixed-results.zip')
    args = p.parse_args()

    director_path = Path(args.director)
    narrative_path = Path(args.narrative)
    d = load(director_path)['results']['adapter']
    n = load(narrative_path)['results']['adapter']
    dm = d['metrics']
    nm = n['metrics']

    lines = [
        'MyDND v4 fixed evaluation',
        '==========================',
        '',
        'DIRECTOR',
        f"count: {dm.get('count', 0)}",
        f"tool syntax: {pct(dm.get('tool_syntax_rate'))}",
        f"Java contract: {pct(dm.get('java_contract_valid_rate'))}",
        f"action type: {pct(dm.get('action_type_accuracy'))}",
        f"identity fields name/value: {pct(dm.get('identity_fields_accuracy'))}",
        f"all fields exact (strict, details included): {pct(dm.get('all_fields_exact_rate'))}",
        '',
        'Director by expected type:',
    ]
    for name, metrics in dm.get('by_expected_type', {}).items():
        lines.append(
            f"  {name:16s} count={metrics.get('count', 0):3d} "
            f"type={pct(metrics.get('action_type_accuracy')):>8s} "
            f"identity={pct(metrics.get('identity_fields_accuracy')):>8s} "
            f"contract={pct(metrics.get('java_contract_valid_rate')):>8s}"
        )

    failures = [c for c in d.get('cases', []) if not c.get('type_ok') or not c.get('java_contract_valid')]
    lines += ['', f'Director failed/invalid cases: {len(failures)}']
    for case in failures[:120]:
        predicted = case.get('predicted') or {}
        lines.append(
            f"  {case['id']}: expected={case.get('expected_type')} "
            f"got={predicted.get('type', 'NO_TOOL')} name={predicted.get('name', '')!r} "
            f"value={predicted.get('value', '')!r}"
        )

    lines += [
        '',
        'NARRATIVE',
        f"count: {nm.get('count', 0)}",
        f"tool leak: {pct(nm.get('tool_leak_rate'))}",
        f"agency violation: {pct(nm.get('agency_violation_rate'))}",
        f"anchor hit: {pct(nm.get('anchor_hit_rate'))}",
        f"forbidden contradiction: {pct(nm.get('forbidden_violation_rate'))}",
        f"known malformed patterns: {pct(nm.get('known_malformed_pattern_rate'))}",
        f"2-4 sentences: {pct(nm.get('sentence_count_ok_rate'))}",
        f"complete ending: {pct(nm.get('complete_ending_rate'))}",
        f"formal gold OK: {pct(nm.get('gold_ok_rate'))}",
        f"unique outputs: {pct(nm.get('unique_output_rate'))}",
        '',
        'Important: Narrative still requires human reading. The Markdown review contains every answer.',
    ]

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    review_lines = [
        '# MyDND v4 Narrative fixed review',
        '',
        f"Formal gold OK: **{pct(nm.get('gold_ok_rate'))}**",
        '',
        'Автоматические флаги ловят нарушения фактов и несколько известных грамматических ошибок, '
        'но окончательная оценка русского текста остаётся ручной.',
        '',
    ]
    for case in n.get('cases', []):
        flags = []
        if not case.get('anchor_hit'):
            flags.append('anchor')
        if case.get('forbidden_hits'):
            flags.append('forbidden=' + ','.join(case['forbidden_hits']))
        if case.get('malformed_hits'):
            flags.append('grammar=' + ','.join(case['malformed_hits']))
        if not case.get('sentence_count_ok'):
            flags.append(f"sentences={case.get('sentence_count')}")
        if not case.get('ends_with_punctuation'):
            flags.append('ending')
        status = 'OK' if case.get('gold_ok') else 'CHECK: ' + '; '.join(flags)
        review_lines += [
            f"## {case['id']} — {status}",
            '',
            '**Промпт**',
            '',
            '```text',
            case.get('input', ''),
            '```',
            '',
            '**Ответ модели**',
            '',
            case.get('output', ''),
            '',
        ]

    review_path = Path(args.review)
    review_path.write_text('\n'.join(review_lines), encoding='utf-8')

    zip_path = Path(args.zip_path)
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (summary_path, review_path, director_path, narrative_path):
            archive.write(path, arcname=path.name)

    print(summary_path.read_text(encoding='utf-8'))
    print(f'Review saved to: {review_path.resolve()}')
    print(f'Archive saved to: {zip_path.resolve()}')


if __name__ == '__main__':
    main()
