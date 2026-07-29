#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description='Create a new MyDND dataset pack template.')
    parser.add_argument('name', help='Pack name, for example director_inventory_v4')
    parser.add_argument('--kind', choices=('director', 'narrative'), default='director')
    args = parser.parse_args()

    safe = re.sub(r'[^a-zA-Z0-9_-]+', '_', args.name).strip('_').lower()
    if not safe:
        raise SystemExit('Invalid pack name')
    path = Path('datasets/packs') / f'{safe}.jsonl'
    if path.exists():
        raise SystemExit(f'{path} already exists')

    if args.kind == 'director':
        row = {
            'id': f'{safe}_0001',
            'kind': 'DIRECTOR',
            'family': f'{safe}_family_0001',
            'split': 'auto',
            'mode': 'PLAYER_ACTION',
            'current_scene': 'Краткое описание текущей сцены.',
            'world': 'Краткое описание мира.',
            'character': 'Герой.',
            'summary': '',
            'recent_events': [],
            'relevant_facts': [],
            'active_situations': '',
            'state': {
                'location': 'Локация', 'hp': '10/10', 'money': '0',
                'inventory': [], 'npcs': [], 'quests': [], 'world_events': [],
                'abilities': [], 'effects': [], 'action_hint': 'NONE'
            },
            'player_action': 'Я беру предмет со стола и оставляю себе.',
            'target': {
                'type': 'INV_ADD', 'name': 'Предмет', 'value': '',
                'details': 'Предмет получен.'
            },
            'note': 'Replace this template row with real examples.'
        }
    else:
        row = {
            'id': f'{safe}_0001',
            'kind': 'NARRATIVE',
            'family': f'{safe}_family_0001',
            'split': 'auto',
            'expected': {'kind': 'NARRATIVE', 'anchors': ['дверь']},
            'messages': [
                {'role': 'system', 'content': '<MODE_NARRATOR>\nТы мастер мрачной RPG. Продолжи сцену кратко. Не решай за игрока. Не печатай tool-call.'},
                {'role': 'user', 'content': 'CURRENT_SCENE:\nВ каменной стене видна старая дверь.\n\nPLAYER_ACTION:\nЯ прислушиваюсь.'},
                {'role': 'assistant', 'content': 'За старой дверью один раз скрипит доска, затем снова наступает тишина. Из щели тянет холодным воздухом.'}
            ]
        }

    path.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Created: {path}')
    print('Edit the file, then run: ./mydnd.sh prepare')


if __name__ == '__main__':
    main()
