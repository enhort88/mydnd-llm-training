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

OUT_DIR = Path('datasets/holdout')
ACTION_TYPES = [
    'DONE', 'CHECK', 'INV_ADD', 'INV_REMOVE', 'HP', 'MONEY',
    'NPC_UPSERT', 'NPC_MEMORY', 'NPC_STATUS',
    'WORLD_ADD', 'WORLD_UPDATE', 'WORLD_RESOLVE',
    'QUEST_START', 'QUEST_UPDATE', 'QUEST_COMPLETE', 'QUEST_FAIL',
    'ABILITY_ADD', 'ABILITY_UPDATE', 'ABILITY_REMOVE',
    'EFFECT_ADD', 'EFFECT_REMOVE', 'LOCATION',
]
CHECK_TYPES = ['STR', 'DEX', 'INT', 'CHA']
MEMORY_VALUES = ['GOOD', 'BAD', 'NEUTRAL']
STATUS_VALUES = ['ALLY', 'HOSTILE', 'MISSING', 'INACTIVE']
ABILITY_VALUES = ['SKILL', 'SPELL', 'TRAIT', 'POWER']

NAMES = ['Марна', 'Торек', 'Ивен', 'Сайра', 'Олден', 'Рута', 'Ферн', 'Келия']
ITEMS = [
    'медный жетон дозорного', 'треснувшая линза', 'ключ из чёрного железа',
    'письмо с сургучной печатью', 'серебряная игла', 'карта затопленных тоннелей',
]
LOCATIONS = [
    'Арка соляных ветров', 'Нижний архив', 'Колодец без отражения',
    'Галерея погасших гербов', 'Северная караульня', 'Пристань мёртвых фонарей',
]
QUESTS = [
    'Долг перед звонарём', 'Свидетель из нижнего архива', 'Печать на северных воротах',
    'След лодочника', 'Три имени на меди', 'Последняя карта тоннелей',
]
EVENTS = [
    'Проседание северной дамбы', 'Исчезновение ночных лодок', 'Пепельный мор',
    'Молчание сторожевых колоколов', 'Заражение колодцев', 'Обвал старой дороги',
]
ABILITIES = [
    'Слух камня', 'Тихий шаг', 'Касание пепла', 'Знак искры', 'Память следопыта', 'Круг защиты',
]
EFFECTS = ['Лихорадка', 'Немота', 'Ослепление', 'Защита печати', 'Слабость', 'Кровотечение']


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def target(kind: str, name: str = '', value: str = '', details: str = '') -> dict:
    return {'type': kind, 'name': name, 'value': value, 'details': details}


def base_state(index: int) -> dict:
    location = LOCATIONS[index % len(LOCATIONS)]
    npc = NAMES[(index * 3) % len(NAMES)]
    return {
        'location': location,
        'hp': f'{10 + (index % 8)}/20',
        'money': str(12 + index % 40),
        'inventory': [ITEMS[index % len(ITEMS)]],
        'npcs': [f'{npc} | ACTIVE | HP 9/9 | {location} | Наблюдает за сценой.'],
        'quests': [],
        'world_events': [],
        'abilities': ['Наблюдательность | SKILL'],
        'effects': [],
        'action_hint': 'NONE',
    }


def director_raw(index: int, kind: str) -> dict:
    state = base_state(index)
    npc = NAMES[index % len(NAMES)]
    item = ITEMS[(index * 2) % len(ITEMS)]
    location = LOCATIONS[(index * 5) % len(LOCATIONS)]
    quest = QUESTS[(index * 7) % len(QUESTS)]
    event = EVENTS[(index * 11) % len(EVENTS)]
    ability = ABILITIES[(index * 13) % len(ABILITIES)]
    effect = EFFECTS[(index * 17) % len(EFFECTS)]
    action = ''
    expected = target('DONE')

    if kind == 'DONE':
        action = 'Я остаюсь на месте и прислушиваюсь. Ничего не беру, не трачу и состояние мира не меняю.'
    elif kind == 'CHECK':
        attr = CHECK_TYPES[index % len(CHECK_TYPES)]
        dc = 11 + index % 8
        action = (
            f'Я пытаюсь пройти по рушащемуся карнизу. До определения исхода нужна проверка '
            f'{attr} сложности {dc}; кубик ещё не брошен.'
        )
        expected = target('CHECK', attr, str(dc), 'Опасный переход по рушащемуся карнизу.')
    elif kind == 'INV_ADD':
        action = f'Я поднимаю предмет «{item}» и кладу его в свой инвентарь.'
        expected = target('INV_ADD', item, '', f'Получен предмет: {item}.')
    elif kind == 'INV_REMOVE':
        if item not in state['inventory']:
            state['inventory'].append(item)
        action = f'Я отдаю предмет «{item}» и он больше не находится в моём инвентаре.'
        expected = target('INV_REMOVE', item, '', f'Потерян предмет: {item}.')
    elif kind == 'HP':
        delta = [-5, -3, -2, 2, 4][index % 5]
        action = f'Изменение уже подтверждено: HP персонажа PLAYER меняется ровно на {delta:+d}.'
        expected = target('HP', 'PLAYER', f'{delta:+d}', 'Подтверждённое изменение здоровья.')
    elif kind == 'MONEY':
        delta = [-17, -8, 6, 14][index % 4]
        action = f'Расчёт завершён: деньги PLAYER меняются ровно на {delta:+d} монет.'
        expected = target('MONEY', 'PLAYER', f'{delta:+d}', 'Подтверждённый денежный расчёт.')
    elif kind == 'NPC_UPSERT':
        state['npcs'] = []
        action = f'В сцене впервые появляется новый NPC по имени {npc}; раньше его не было среди известных NPC.'
        expected = target('NPC_UPSERT', npc, '', f'Впервые появился NPC {npc}.')
    elif kind == 'NPC_MEMORY':
        state['npcs'] = [f'{npc} | ACTIVE | HP 9/9 | {state["location"]} | Говорит с героем.']
        value = MEMORY_VALUES[index % len(MEMORY_VALUES)]
        meaning = {'GOOD': 'добрый и полезный', 'BAD': 'враждебный и вредный', 'NEUTRAL': 'нейтральный'}[value]
        action = f'{npc} запоминает этот поступок как {meaning}. Значение памяти должно быть {value}.'
        expected = target('NPC_MEMORY', npc, value, f'{npc} запомнил поступок героя как {value}.')
    elif kind == 'NPC_STATUS':
        state['npcs'] = [f'{npc} | ACTIVE | HP 9/9 | {state["location"]} | Говорит с героем.']
        value = STATUS_VALUES[index % len(STATUS_VALUES)]
        action = f'Новый подтверждённый статус NPC {npc}: {value}.'
        expected = target('NPC_STATUS', npc, value, f'Статус {npc} изменён на {value}.')
    elif kind == 'WORLD_ADD':
        importance = 1 + index % 3
        action = f'Начинается новое долгосрочное событие мира «{event}» с важностью {importance}.'
        expected = target('WORLD_ADD', event, str(importance), 'Новое долгосрочное событие мира.')
    elif kind == 'WORLD_UPDATE':
        importance = 1 + index % 3
        state['world_events'] = [f'{event} | ACTIVE | IMPORTANCE {importance} | Продолжается.']
        action = f'У существующего события «{event}» подтверждено новое обстоятельство; важность остаётся {importance}.'
        expected = target('WORLD_UPDATE', event, str(importance), 'Подтверждено новое обстоятельство события.')
    elif kind == 'WORLD_RESOLVE':
        state['world_events'] = [f'{event} | ACTIVE | IMPORTANCE 2 | Продолжается.']
        action = f'Причина события «{event}» окончательно устранена; событие завершено.'
        expected = target('WORLD_RESOLVE', event, '', 'Событие окончательно завершено.')
    elif kind == 'QUEST_START':
        action = f'Я официально принимаю новый квест «{quest}».'
        expected = target('QUEST_START', quest, '', 'Квест принят.')
    elif kind == 'QUEST_UPDATE':
        state['quests'] = [f'{quest} | ACTIVE | Найти свидетельство.']
        action = f'Для активного квеста «{quest}» найдена подтверждённая новая улика.'
        expected = target('QUEST_UPDATE', quest, '', 'Найдена подтверждённая новая улика.')
    elif kind == 'QUEST_COMPLETE':
        state['quests'] = [f'{quest} | ACTIVE | Найти свидетельство.']
        action = f'Все условия активного квеста «{quest}» выполнены; квест подтверждённо завершён успешно.'
        expected = target('QUEST_COMPLETE', quest, '', 'Квест успешно завершён.')
    elif kind == 'QUEST_FAIL':
        state['quests'] = [f'{quest} | ACTIVE | Найти свидетельство.']
        action = f'Цель активного квеста «{quest}» окончательно стала недостижима; квест подтверждённо провален.'
        expected = target('QUEST_FAIL', quest, '', 'Квест окончательно провален.')
    elif kind == 'ABILITY_ADD':
        value = ABILITY_VALUES[index % len(ABILITY_VALUES)]
        action = f'Герой освоил новую способность «{ability}» категории {value}.'
        expected = target('ABILITY_ADD', ability, value, 'Новая способность освоена.')
    elif kind == 'ABILITY_UPDATE':
        old_value = ABILITY_VALUES[(index + 1) % len(ABILITY_VALUES)]
        new_value = ABILITY_VALUES[index % len(ABILITY_VALUES)]
        state['abilities'] = [f'{ability} | {old_value}']
        action = f'Категория существующей способности «{ability}» подтверждённо меняется на {new_value}.'
        expected = target('ABILITY_UPDATE', ability, new_value, 'Категория способности обновлена.')
    elif kind == 'ABILITY_REMOVE':
        state['abilities'] = [f'{ability} | SKILL']
        action = f'Герой окончательно утрачивает существующую способность «{ability}».'
        expected = target('ABILITY_REMOVE', ability, '', 'Способность окончательно утрачена.')
    elif kind == 'EFFECT_ADD':
        action = f'На героя подтверждённо начинает действовать новый эффект «{effect}».'
        expected = target('EFFECT_ADD', effect, '', 'Эффект начал действовать.')
    elif kind == 'EFFECT_REMOVE':
        state['effects'] = [effect]
        action = f'Существующий эффект «{effect}» полностью прекращает действовать.'
        expected = target('EFFECT_REMOVE', effect, '', 'Эффект полностью снят.')
    elif kind == 'LOCATION':
        action = f'Переход завершён безопасно: герой вошёл в новую локацию «{location}».'
        expected = target('LOCATION', location, '', f'Герой вошёл в локацию «{location}».')
    else:
        raise ValueError(kind)

    return {
        'id': f'v4fixed_d_{index:05d}',
        'kind': 'DIRECTOR',
        'family': f'v4fixed_d_{index:05d}',
        'mode': 'PLAYER_ACTION',
        'current_scene': f'Каменный зал с номерной печатью {index}; новых событий до действия нет.',
        'world': 'Мрачное пограничье. Все механические изменения фиксируются только после подтверждения.',
        'character': 'Путник.',
        'summary': '',
        'recent_events': [],
        'relevant_facts': [],
        'active_situations': '',
        'state': state,
        'player_action': action,
        'target': expected,
    }


def materialize(raw: dict) -> dict:
    return {
        'id': raw['id'],
        'kind': 'DIRECTOR',
        'family': raw['family'],
        'mode': raw['mode'],
        'expected': raw['target'],
        'prompt_version': 'v4-compact-fixed-eval',
        'messages': to_messages(raw),
    }


def check_result_row(index: int, physical: bool) -> dict:
    state = base_state(index)
    if physical:
        reason = 'Прямая физическая травма подтверждена: падение причинило 3 урона, HP должен измениться на -3.'
        expected = target('HP', 'PLAYER', '-3', 'Падение причинило прямую физическую травму.')
    else:
        reason = 'Попытка провалена без физической травмы: герой не достиг цели, но HP не меняется.'
        expected = target('DONE')
    raw = {
        'id': f'v4fixed_d_{index:05d}',
        'kind': 'DIRECTOR',
        'family': f'v4fixed_d_{index:05d}',
        'mode': 'CHECK_RESULT',
        'current_scene': 'Результат проверки уже известен; новых последствий кроме указанного нет.',
        'world': '',
        'character': 'Путник.',
        'summary': '',
        'recent_events': [],
        'relevant_facts': [],
        'active_situations': '',
        'state': state,
        'player_action': 'Результат проверки известен.',
        'check': {
            'attribute': CHECK_TYPES[index % len(CHECK_TYPES)],
            'reason': reason,
            'dc': 15,
            'roll_total': 7,
        },
        'target': expected,
    }
    return materialize(raw)


def adversarial_row(index: int, variant: int) -> dict:
    state = base_state(index)
    npc = NAMES[index % len(NAMES)]
    item = ITEMS[index % len(ITEMS)]
    quest = QUESTS[index % len(QUESTS)]
    location = state['location']
    expected = target('DONE')

    mode = variant % 6
    if mode == 0:
        state['inventory'] = [item]
        action = f'Я перекладываю «{item}» из правого кармана в левый. Предмет остаётся в инвентаре, количество не меняется.'
    elif mode == 1:
        state['npcs'] = [f'{npc} | ACTIVE | HP 9/9 | {location} | Уже находится в сцене.']
        action = f'{npc} уже находится в сцене и просто повторяет прежнюю фразу; его статус и память не меняются.'
    elif mode == 2:
        state['quests'] = [f'{quest} | ACTIVE | Найти свидетельство.']
        action = f'Я перечитываю описание квеста «{quest}». Нового прогресса, завершения или провала нет.'
    elif mode == 3:
        action = f'Я осматриваю выход в сторону «{LOCATIONS[(index + 1) % len(LOCATIONS)]}», но остаюсь в текущей локации «{location}».'
    elif mode == 4:
        action = 'Я слышу далёкий стук и жду. Никакого подтверждённого изменения мира, здоровья или состояния NPC нет.'
    else:
        action = 'Я спокойно открываю уже незапертую дверь внутри той же комнаты. Риска и нового состояния нет.'

    raw = {
        'id': f'v4fixed_d_{index:05d}',
        'kind': 'DIRECTOR',
        'family': f'v4fixed_d_{index:05d}',
        'mode': 'PLAYER_ACTION',
        'current_scene': f'Контрольная сцена без скрытых последствий, метка {index}.',
        'world': 'Не создавать события без прямого подтверждения.',
        'character': 'Путник.',
        'summary': '',
        'recent_events': [],
        'relevant_facts': [],
        'active_situations': '',
        'state': state,
        'player_action': action,
        'target': expected,
    }
    return materialize(raw)


def director_rows(per_type: int, check_result_count: int, adversarial_count: int) -> list[dict]:
    rows: list[dict] = []
    index = 0
    for kind in ACTION_TYPES:
        for _ in range(per_type):
            index += 1
            rows.append(materialize(director_raw(index, kind)))
    for i in range(check_result_count):
        index += 1
        rows.append(check_result_row(index, physical=(i % 2 == 0)))
    for i in range(adversarial_count):
        index += 1
        rows.append(adversarial_row(index, i))
    return rows


NARRATIVE_SCENES = [
    {
        'scene': 'Нижний архив полностью тёмный; единственный свет даёт зелёный гриб на каменной полке. На столе лежит медный жетон.',
        'action': 'Я осторожно прислушиваюсь, не сходя с места.',
        'anchors': ['зелёный гриб', 'медный жетон'],
        'forbidden': ['солнце', 'рассвет', 'лампа', 'факел'],
        'reference': 'Зелёный гриб отбрасывает слабое сияние на край медного жетона. Из-за дальнего стеллажа доносится сухой шорох, но в темноте ничто больше не движется.',
    },
    {
        'scene': 'На открытой соляной равнине стоит полдень. Воздух сухой, небо безоблачно, вокруг нет укрытий и воды.',
        'action': 'Я осматриваю горизонт.',
        'anchors': ['соляной равнине', 'горизонт'],
        'forbidden': ['дождь', 'снег', 'ночь', 'лес'],
        'reference': 'Белая соль режет глаза отражённым светом, а линия горизонта дрожит от жара. Вдалеке проступает тёмная точка, слишком неподвижная для путника.',
    },
    {
        'scene': 'В караульне горит ровно одна масляная лампа. Торек молчит у двери, а на полу лежит треснувшая линза.',
        'action': 'Я спрашиваю Торека, кому принадлежала линза.',
        'anchors': ['Торек', 'линз'],
        'forbidden': ['две лампы', 'солнечный свет'],
        'reference': 'Торек не сразу отводит взгляд от треснувшей линзы. Пламя единственной лампы дрожит, когда он тихо произносит имя прежнего дозорного.',
    },
    {
        'scene': 'Подземный канал затоплен по колено. Вода неподвижна, мост разрушен, других существ поблизости нет.',
        'action': 'Я проверяю воду концом посоха.',
        'anchors': ['вода', 'посох'],
        'forbidden': ['толпа', 'стражник', 'лошадь'],
        'reference': 'Конец посоха касается поверхности, и по неподвижной воде расходятся тяжёлые круги. У основания разрушенного моста что-то металлическое на миг отвечает глухим звоном.',
    },
    {
        'scene': 'В часовне нет огня. Через разбитое окно падает холодный лунный свет; серебряная игла лежит на алтаре.',
        'action': 'Я рассматриваю иглу, не касаясь её.',
        'anchors': ['серебряная игла', 'лунн'],
        'forbidden': ['солнце', 'пламя', 'лампа'],
        'reference': 'Лунный свет скользит по серебряной игле и собирается на её кончике бледной точкой. На камне вокруг алтаря заметен тонкий круг, будто иглу недавно передвигали.',
    },
    {
        'scene': 'Сайра стоит у закрытого окна. За стеклом бушует метель, но внутри комнаты тепло и сухо.',
        'action': 'Я спрашиваю Сайру, почему окно заперто.',
        'anchors': ['Сайра', 'окн'],
        'forbidden': ['дождь внутри', 'снег на полу', 'жара'],
        'reference': 'Сайра проводит пальцем по холодной раме и не смотрит на метель. Она отвечает тихо: окно заперли не от ветра, а от того, что однажды постучало снаружи.',
    },
    {
        'scene': 'В библиотеке запрещено говорить. Здесь нет людей; между книгами на кафедре лежит письмо с сургучной печатью.',
        'action': 'Я бесшумно осматриваю печать.',
        'anchors': ['письм', 'печат'],
        'forbidden': ['говорит', 'кричит', 'толпа'],
        'reference': 'Сургуч на письме покрыт тонкой сеткой трещин, но печать не вскрыта. Между страницами ближайшей книги шевелится узкая полоска бумаги, хотя воздух в библиотеке неподвижен.',
    },
    {
        'scene': 'У пристани ночь, все фонари погашены. В воде отражаются только звёзды; лодок у причала нет.',
        'action': 'Я ищу следы недавней лодки.',
        'anchors': ['причал', 'след'],
        'forbidden': ['солнце', 'горящий фонарь', 'лодка у причала'],
        'reference': 'На мокрых досках причала видна свежая дуга от каната. Чуть ниже вода ещё колеблется, словно лодка отошла совсем недавно.',
    },
    {
        'scene': 'В кузнице давно не работали: горн холодный, угли серые, воздух пахнет ржавчиной. На верстаке лежит ключ из чёрного железа.',
        'action': 'Я беру ключ двумя пальцами и рассматриваю его.',
        'anchors': ['ключ', 'холод'],
        'forbidden': ['пылающий горн', 'кузнец работает', 'жар'],
        'reference': 'Чёрное железо остаётся холодным даже в ладони. На бородке ключа проступает тонкая красная пыль, похожая не на ржавчину, а на высохшую глину.',
    },
    {
        'scene': 'На лесной тропе раннее утро. Дождь только закончился, листья мокрые, следы на земле свежие.',
        'action': 'Я наклоняюсь к следам, не наступая на них.',
        'anchors': ['след', 'мокр'],
        'forbidden': ['сухая пыль', 'полдень', 'снег'],
        'reference': 'Вода ещё собирается в углублениях свежих следов. Один отпечаток глубже остальных, будто тот, кто шёл по тропе, внезапно остановился и обернулся.',
    },
    {
        'scene': 'В склепе слышно только капли воды. Рута держит погасшую свечу; саркофаг закрыт и не повреждён.',
        'action': 'Я спрашиваю Руту, слышала ли она что-нибудь ещё.',
        'anchors': ['Рута', 'капл'],
        'forbidden': ['горящая свеча', 'открытый саркофаг', 'солнечный свет'],
        'reference': 'Рута крепче сжимает погасшую свечу и вслушивается в размеренный стук капель. После паузы она указывает на саркофаг: один звук пришёл изнутри и не повторился.',
    },
    {
        'scene': 'Башня качается под сильным ветром. Внутри никого нет; карта затопленных тоннелей прибита к стене четырьмя гвоздями.',
        'action': 'Я проверяю, не скрыто ли что-нибудь за картой.',
        'anchors': ['карт', 'стен'],
        'forbidden': ['разговор', 'толпа', 'полный штиль'],
        'reference': 'Карта шуршит под порывами ветра, но гвозди держат её крепко. За нижним краем обнаруживается узкая выемка в камне, достаточно глубокая для сложенного листа.',
    },
]


def narrative_rows(count: int) -> list[dict]:
    rows: list[dict] = []
    actions = [
        'Я остаюсь на месте и наблюдаю.',
        'Я осторожно прислушиваюсь.',
        'Я рассматриваю ближайший предмет, не касаясь его.',
        'Я задаю короткий вопрос, не предпринимая других действий.',
    ]
    for i in range(count):
        base = NARRATIVE_SCENES[i % len(NARRATIVE_SCENES)]
        action = base['action'] if i < len(NARRATIVE_SCENES) else actions[i % len(actions)]
        scene = base['scene'] + f' Контрольная метка сцены: {i + 1}.'
        expected = {
            'kind': 'NARRATIVE',
            'anchors': base['anchors'],
            'forbidden': base['forbidden'],
            'min_sentences': 2,
            'max_sentences': 4,
        }
        rows.append({
            'id': f'v4fixed_n_{i + 1:05d}',
            'kind': 'NARRATIVE',
            'family': f'v4fixed_n_{i + 1:05d}',
            'mode': 'NARRATIVE',
            'expected': expected,
            'prompt_version': 'v4-compact-fixed-eval',
            'messages': [
                {'role': 'system', 'content': NARRATOR_SYSTEM_PROMPT},
                {'role': 'user', 'content': f'SCENE: {scene}\nACTION: {action}'},
                {'role': 'assistant', 'content': base['reference']},
            ],
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate deterministic v4 evaluation holdout.')
    parser.add_argument('--per-type', type=int, default=10)
    parser.add_argument('--check-result', type=int, default=40)
    parser.add_argument('--adversarial', type=int, default=60)
    parser.add_argument('--narrative', type=int, default=48)
    args = parser.parse_args()

    director = director_rows(args.per_type, args.check_result, args.adversarial)
    narrative = narrative_rows(args.narrative)
    write_jsonl(OUT_DIR / 'v4_director_fixed.jsonl', director)
    write_jsonl(OUT_DIR / 'v4_narrative_fixed.jsonl', narrative)
    print(f'Wrote fixed holdout: director={len(director)}, narrative={len(narrative)}')
    print('Every Director identity field is explicitly recoverable from the prompt.')


if __name__ == '__main__':
    main()
