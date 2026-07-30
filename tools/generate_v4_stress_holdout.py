#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.contract_v4 import NARRATOR_SYSTEM_PROMPT, to_messages

OUT = Path('datasets/holdout')
TYPES = [
    'DONE','CHECK','INV_ADD','INV_REMOVE','HP','MONEY','NPC_UPSERT','NPC_MEMORY','NPC_STATUS',
    'WORLD_ADD','WORLD_UPDATE','WORLD_RESOLVE','QUEST_START','QUEST_UPDATE','QUEST_COMPLETE','QUEST_FAIL',
    'ABILITY_ADD','ABILITY_UPDATE','ABILITY_REMOVE','EFFECT_ADD','EFFECT_REMOVE','LOCATION'
]
NAMES = ['Адела','Борн','Веста','Гален','Дея','Ерн','Жара','Зорн','Ирма','Краст','Лем','Нора']
ITEMS = ['костяной ключ','осколок зеркала','запечатанный свиток','оловянный жетон','синяя лента','пустой пузырёк']
LOCS = ['Пепельный двор','Склеп дозорного','Зал сломанных часов','Тоннель под рынком','Башня соляного ветра','Сад без птиц']
QUESTS = ['Тихий свидетель','Шестой колокол','Дорога из соли','Имя на стекле','Пустая корона','След в золе']
EVENTS = ['Чёрный прилив','Молчание колоколов','Падение западной стены','Болезнь садов','Исчезновение лодок','Красный туман']
ABILITIES = [('Касание пепла','POWER'),('Слух камня','TRAIT'),('Тихий шаг','SKILL'),('Знак искры','SPELL')]
EFFECTS = ['Немота','Лихорадка','Защита печати','Слабость','Ослепление']


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def state(rng: random.Random) -> dict:
    loc = rng.choice(LOCS)
    npc = rng.choice(NAMES)
    return {
        'location': loc, 'hp': f'{rng.randint(5, 17)}/20', 'money': str(rng.randint(0, 50)),
        'inventory': rng.sample(ITEMS, k=2),
        'npcs': [f'{npc} | ACTIVE | HP 9/9 | {loc} | Скрывает тревогу.'],
        'quests': [], 'world_events': [], 'abilities': ['Наблюдательность | SKILL'],
        'effects': [], 'action_hint': 'NONE',
    }


def target(kind: str, name: str = '', value: str = '', details: str = '') -> dict:
    return {'type': kind, 'name': name, 'value': value, 'details': details}


def raw_case(index: int, kind: str, rng: random.Random) -> dict:
    st = state(rng)
    npc, item, loc, quest, event = rng.choice(NAMES), rng.choice(ITEMS), rng.choice(LOCS), rng.choice(QUESTS), rng.choice(EVENTS)
    ability, ability_kind = rng.choice(ABILITIES)
    effect = rng.choice(EFFECTS)
    action = ''
    tgt = target('DONE')
    if kind == 'DONE': action = f'Я вспоминаю разговор с {npc}, но ничего не меняю.'
    elif kind == 'CHECK':
        attr = rng.choice(['STR','DEX','INT','CHA']); dc = rng.randint(11,18)
        action = f'Я пытаюсь рискованно добраться до места «{loc}» через разрушенный проход.'
        tgt = target('CHECK', attr, str(dc), 'Опасный переход через разрушенный проход.')
    elif kind == 'INV_ADD': action, tgt = f'Я забираю «{item}» и прячу в сумку.', target(kind,item,'',f'Получен предмет: {item}.')
    elif kind == 'INV_REMOVE':
        st['inventory'].append(item); action, tgt = f'Я отдаю «{item}» владельцу и больше не несу его.', target(kind,item,'',f'Потерян предмет: {item}.')
    elif kind == 'HP':
        delta = rng.choice([-4,-3,-2,2,3]); action, tgt = f'Подтверждено изменение здоровья героя на {delta:+d}.', target(kind,'PLAYER',f'{delta:+d}','Подтверждённое изменение здоровья.')
    elif kind == 'MONEY':
        delta = rng.choice([-15,-7,7,15]); action, tgt = f'Расчёт завершён, деньги героя меняются на {delta:+d}.', target(kind,'PLAYER',f'{delta:+d}','Расчёт завершён.')
    elif kind == 'NPC_UPSERT': action, tgt = f'Впервые появляется {npc}, представляется и остаётся в сцене.', target(kind,npc,'',f'Появился NPC: {npc}.')
    elif kind == 'NPC_MEMORY':
        st['npcs']=[f'{npc} | ACTIVE | HP 9/9 | {st["location"]} | Говорит с героем.']; val=rng.choice(['GOOD','BAD','NEUTRAL'])
        action, tgt = f'{npc} запоминает конкретный поступок героя.', target(kind,npc,val,f'{npc} запомнил поступок героя.')
    elif kind == 'NPC_STATUS':
        st['npcs']=[f'{npc} | ACTIVE | HP 9/9 | {st["location"]} | Говорит с героем.']; val=rng.choice(['ALLY','HOSTILE','MISSING','INACTIVE'])
        action, tgt = f'После события статус {npc} подтверждён как {val}.', target(kind,npc,val,f'Статус {npc}: {val}.')
    elif kind == 'WORLD_ADD': action, tgt = f'Событие «{event}» начинается и надолго меняет область.', target(kind,event,str(rng.randint(1,3)),'Новое долгосрочное событие мира.')
    elif kind == 'WORLD_UPDATE':
        st['world_events']=[f'{event} | ACTIVE | IMPORTANCE 2 | Продолжается.']; action, tgt = f'У события «{event}» появилось подтверждённое новое обстоятельство.', target(kind,event,'2','Появилось новое подтверждённое обстоятельство.')
    elif kind == 'WORLD_RESOLVE':
        st['world_events']=[f'{event} | ACTIVE | IMPORTANCE 2 | Продолжается.']; action, tgt = f'Причина события «{event}» окончательно устранена.', target(kind,event,'','Событие завершено.')
    elif kind == 'QUEST_START': action, tgt = f'Я принимаю официальное поручение «{quest}».', target(kind,quest,'','Поручение принято.')
    elif kind == 'QUEST_UPDATE':
        st['quests']=[f'{quest} | ACTIVE | Найти доказательство.']; action, tgt = f'По квесту «{quest}» найдена новая улика.', target(kind,quest,'','Найдена новая улика.')
    elif kind == 'QUEST_COMPLETE':
        st['quests']=[f'{quest} | ACTIVE | Найти доказательство.']; action, tgt = f'Условие квеста «{quest}» выполнено и подтверждено.', target(kind,quest,'','Квест выполнен.')
    elif kind == 'QUEST_FAIL':
        st['quests']=[f'{quest} | ACTIVE | Найти доказательство.']; action, tgt = f'Цель квеста «{quest}» окончательно стала недостижима.', target(kind,quest,'','Квест провален.')
    elif kind == 'ABILITY_ADD': action, tgt = f'Герой завершает обучение и получает «{ability}».', target(kind,ability,ability_kind,'Способность освоена.')
    elif kind == 'ABILITY_UPDATE':
        st['abilities']=[f'{ability} | {ability_kind}']; val=rng.choice(['SKILL','SPELL','TRAIT','POWER']); action, tgt = f'Категория способности «{ability}» подтверждённо меняется.', target(kind,ability,val,'Способность обновлена.')
    elif kind == 'ABILITY_REMOVE':
        st['abilities']=[f'{ability} | {ability_kind}']; action, tgt = f'Герой окончательно теряет способность «{ability}».', target(kind,ability,'','Способность утрачена.')
    elif kind == 'EFFECT_ADD': action, tgt = f'Эффект «{effect}» действительно начинает действовать на героя.', target(kind,effect,'','Эффект добавлен.')
    elif kind == 'EFFECT_REMOVE':
        st['effects']=[effect]; action, tgt = f'Эффект «{effect}» полностью прекращается.', target(kind,effect,'','Эффект снят.')
    elif kind == 'LOCATION': action, tgt = f'Я безопасно дохожу до локации «{loc}».', target(kind,loc,'',f'Герой вошёл в локацию «{loc}».')
    return {
        'id': f'v4stress_d_{index:05d}', 'kind':'DIRECTOR', 'family':f'v4stress_d_{index:05d}',
        'mode':'PLAYER_ACTION', 'current_scene':f'В помещении стоит резной столб с меткой {index}; слышен далёкий скрип.',
        'world':'Суровое пограничье без устойчивой погоды.', 'character':'Путник.', 'summary':'',
        'recent_events':[], 'relevant_facts':[], 'active_situations':'', 'state':st,
        'player_action':action, 'target':tgt,
    }


def director_rows(count: int, rng: random.Random) -> list[dict]:
    rows=[]
    base = max(1, (count - 100) // len(TYPES))
    index=0
    for kind in TYPES:
        for _ in range(base):
            index += 1
            raw=raw_case(index,kind,rng)
            rows.append({'id':raw['id'],'kind':'DIRECTOR','family':raw['family'],'mode':raw['mode'],'expected':raw['target'],'prompt_version':'v4-compact','messages':to_messages(raw)})
    while len(rows) < count:
        index += 1
        attr=rng.choice(['STR','DEX','INT','CHA']); physical=index%2==0
        st=state(rng)
        raw={
            'id':f'v4stress_d_{index:05d}','kind':'DIRECTOR','family':f'v4stress_d_{index:05d}','mode':'CHECK_RESULT',
            'current_scene':'Под ногами осыпаются камни после завершённой попытки.','world':'','character':'Путник.','summary':'',
            'recent_events':[],'relevant_facts':[],'active_situations':'','state':st,'player_action':'Результат известен.',
            'check':{'attribute':attr,'reason':'провал опасного перехода','dc':15,'roll_total':7},
            'target':target('HP','PLAYER','-3','Падение причинило травму.') if physical else target('DONE'),
        }
        rows.append({'id':raw['id'],'kind':'DIRECTOR','family':raw['family'],'mode':raw['mode'],'expected':raw['target'],'prompt_version':'v4-compact','messages':to_messages(raw)})
    return rows[:count]


def narrative_rows(count: int, rng: random.Random) -> list[dict]:
    rows=[]
    for i in range(1,count+1):
        loc=LOCS[i%len(LOCS)]; npc=NAMES[(i*3)%len(NAMES)]; item=ITEMS[(i*5)%len(ITEMS)]
        scene=f'В локации «{loc}» горит одна лампа. {npc} стоит у стены; рядом лежит {item}. На полу видна метка {i}.'
        action=rng.choice(['Я прислушиваюсь.','Я осматриваю стены.','Я спрашиваю, кто был здесь раньше.','Я остаюсь на месте и наблюдаю.'])
        answer=(f'Свет лампы дрожит на стене, выделяя метку {i}. {npc} переводит взгляд на {item}, '
                f'а из глубины локации «{loc}» доносится один короткий скрип, после которого снова становится тихо.')
        rows.append({'id':f'v4stress_n_{i:05d}','kind':'NARRATIVE','family':f'v4stress_n_{i:05d}','mode':'NARRATIVE',
                     'expected':{'kind':'NARRATIVE','anchors':[loc,npc,item]},'prompt_version':'v4-compact',
                     'messages':[{'role':'system','content':NARRATOR_SYSTEM_PROMPT},
                                 {'role':'user','content':f'SCENE: {scene}\nACTION: {action}'},
                                 {'role':'assistant','content':answer}]})
    return rows


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--director',type=int,default=2000)
    parser.add_argument('--narrative',type=int,default=500)
    parser.add_argument('--seed',type=int,default=404041)
    args=parser.parse_args()
    rng=random.Random(args.seed)
    d=director_rows(args.director,rng); n=narrative_rows(args.narrative,rng)
    write(OUT/'v4_director_stress.jsonl',d); write(OUT/'v4_narrative_stress.jsonl',n)
    print(f'Wrote stress holdout: director={len(d)}, narrative={len(n)}')


if __name__=='__main__':
    main()
