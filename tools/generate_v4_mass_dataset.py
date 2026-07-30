#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / 'datasets' / 'packs'
SEED = 240730

NAMES = ['Мара','Рейн','Сорен','Келл','Иона','Дорн','Вейла','Хальд','Тарн','Лиора','Брен','Эсма','Гарр','Нив','Орин','Фара','Мелв','Сайра','Ворон','Пепел','Рада','Тир','Морн','Элин']
ROLES = ['охотник','капитан','лекарь','проводник','жрец','писарь','разведчик','кузнец','лодочник','алхимик','контрабандист','травник']
ITEMS = ['ржавый ключ','серебряная игла','обрывок карты','письмо капитана','медный жетон','фляга с маслом','чёрное перо','сломанный амулет','верёвка','факел','старый компас','печатка дозорного']
LOCATIONS = ['Старая застава','Нижняя галерея','Северный двор','Крипта','Архив','Каменоломня','Болотная тропа','Речной брод','Заброшенная часовня','Городские ворота','Подземный ход','Старая кузница']
QUESTS = ['Пропавший гонец','Печать аббата','Зверь из оврага','Украденный колокол','Долг кузнеца','Слепая башня','Чёрная вода','Пепел на снегу','Последний мост','Кости святого']
EVENTS = ['Пожар на заставе','Обвал старого моста','Чума в Нижнем квартале','Наводнение у мельницы','Мятеж шахтёров','Блокада гавани','Зимняя буря','Осквернение источника']
ABILITIES = [('Взлом замков','SKILL'),('Шёпот теней','SPELL'),('Крепкая спина','TRAIT'),('Огненная метка','POWER')]
EFFECTS = ['Отравление','Благословение','Страх','Оглушение','Проклятие']
CHECKS = [('DEX','перепрыгнуть трещину в мосту'),('STR','поднять каменную плиту'),('INT','расшифровать печать'),('CHA','убедить дозорного'),('DEX','пройти по мокрому карнизу'),('STR','удержать падающую балку')]


DETAIL_ADJECTIVES = [
    'потемневший', 'треснувший', 'обугленный', 'ржавый', 'выцветший', 'запылённый',
    'перевёрнутый', 'надколотый', 'покосившийся', 'закопчённый', 'поцарапанный',
    'намокший', 'помятый', 'окованный', 'резной', 'оплавленный', 'потёртый',
    'запечатанный', 'позеленевший', 'перевязанный',
]
DETAIL_NOUNS = [
    'фонарь', 'щит', 'ящик', 'подсвечник', 'колокол', 'кувшин', 'указатель', 'сундук',
    'табурет', 'шлем', 'барельеф', 'ларец', 'крюк', 'котелок', 'барабан', 'светильник',
    'столб', 'замок', 'медальон', 'футляр',
]
DETAIL_MARKS = [
    'со следом воска', 'с тремя насечками', 'с трещиной у края', 'с засохшей глиной',
    'с обрывком красной нити', 'с пятном свежей копоти', 'с прилипшим пером',
    'с выцарапанным кругом', 'с каплей тёмной смолы', 'с запахом горьких трав',
    'с полосой серебристой пыли', 'с отпечатком маленькой ладони', 'с куском синей ткани',
    'с застывшей каплей масла', 'с тонкой цепочкой', 'с выцветшей печатью',
    'с обломком стрелы', 'с медной скобой', 'с белёсым налётом', 'с узлом чёрной бечёвки',
]

DIRECTOR_ACTION_TEMPLATES = {
    'DONE': [
        'Я осматриваюсь, ничего не трогая.',
        'Я жду и прислушиваюсь, оставаясь на месте.',
        'Я обдумываю следующий шаг, но пока ничего не предпринимаю.',
        'Я задаю общий вопрос и не совершаю действия, меняющего состояние мира.',
        'Я проверяю свои вещи и возвращаю их на прежние места.',
    ],
    'CHECK': [
        'Я пытаюсь {goal}.',
        'Я рискую и пробую {goal}.',
        'Не откладывая, я решаю {goal}.',
        'Я предпринимаю опасную попытку: {goal}.',
    ],
}


def natural_detail(index: int) -> str:
    """Return a deterministic natural detail. The first 8,000 values are unique."""
    a = DETAIL_ADJECTIVES[index % len(DETAIL_ADJECTIVES)]
    n = DETAIL_NOUNS[(index // len(DETAIL_ADJECTIVES)) % len(DETAIL_NOUNS)]
    m = DETAIL_MARKS[(index // (len(DETAIL_ADJECTIVES) * len(DETAIL_NOUNS))) % len(DETAIL_MARKS)]
    return f'{a} {n} {m}'

DIRECTOR_TYPES = [
    'DONE','CHECK','INV_ADD','INV_REMOVE','HP','MONEY','NPC_UPSERT','NPC_MEMORY','NPC_STATUS',
    'WORLD_ADD','WORLD_UPDATE','WORLD_RESOLVE','QUEST_START','QUEST_UPDATE','QUEST_COMPLETE','QUEST_FAIL',
    'ABILITY_ADD','ABILITY_UPDATE','ABILITY_REMOVE','EFFECT_ADD','EFFECT_REMOVE','LOCATION'
]


def split_for(family: str, eval_percent: int = 20) -> str:
    value = int(hashlib.sha1(family.encode('utf-8')).hexdigest()[:8], 16) % 100
    return 'eval' if value < eval_percent else 'train'


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def base_state(rng: random.Random) -> dict:
    location = rng.choice(LOCATIONS)
    npc = rng.choice(NAMES)
    return {
        'location': location,
        'hp': f"{rng.randint(6,18)}/20",
        'money': str(rng.randint(0,80)),
        'inventory': rng.sample(ITEMS, k=rng.randint(1,4)),
        'npcs': [f'{npc} | ACTIVE | HP 10/10 | {location} | Наблюдает за героем.'],
        'quests': [], 'world_events': [],
        'abilities': ['Внимательность | SKILL'], 'effects': [], 'action_hint': 'NONE',
    }


def target(t: str, name: str = '', value: str = '', details: str = '') -> dict:
    return {'type': t, 'name': name, 'value': value, 'details': details}


def director_row(rid: str, family: str, action: str, tgt: dict, rng: random.Random, *, state=None, mode='PLAYER_ACTION', check=None) -> dict:
    loc = (state or {}).get('location') or rng.choice(LOCATIONS)
    digits = ''.join(ch for ch in rid if ch.isdigit())
    detail = natural_detail(int(digits or '0'))
    row = {
        'id': rid, 'kind': 'DIRECTOR', 'family': family, 'split': split_for(family), 'mode': mode,
        'current_scene': (
            f'Сумерки сгущаются. Герой находится в локации «{loc}». '
            f'Рядом слышны редкие шаги и скрип дерева. У стены стоит {detail}.'
        ),
        'world': 'Мрачное пограничье, где старые дороги небезопасны.',
        'character': 'Путник, человек, авантюрист.', 'summary': '', 'recent_events': [],
        'relevant_facts': [], 'active_situations': '', 'state': state or base_state(rng),
        'player_action': action, 'target': tgt, 'note': 'v4 mass deterministic synthetic hard case'
    }
    if check is not None:
        row['check'] = check
    return row


def make_director(count: int, rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    per_type = max(1, count // len(DIRECTOR_TYPES))
    serial = 0

    def add(family: str, action: str, tgt: dict, **kw):
        nonlocal serial
        serial += 1
        rows.append(director_row(f'v4d_{serial:06d}', family, action, tgt, rng, **kw))

    for typ in DIRECTOR_TYPES:
        for i in range(per_type):
            fam = f'v4_{typ.lower()}_{i:05d}'
            item = rng.choice(ITEMS); npc = rng.choice(NAMES); role = rng.choice(ROLES)
            loc = rng.choice(LOCATIONS); quest = rng.choice(QUESTS); event = rng.choice(EVENTS)
            ability, ability_kind = rng.choice(ABILITIES); effect = rng.choice(EFFECTS)
            st = base_state(rng)
            if typ == 'DONE':
                action = rng.choice([
                    'Я осматриваюсь, ничего не трогая.', 'Я жду и прислушиваюсь.',
                    f'Я вспоминаю слух о {npc}, но ничего не предпринимаю.',
                    f'Я перекладываю предмет «{item}» из одного кармана в другой.',
                    f'Я обсуждаю возможность пойти в «{loc}», но остаюсь на месте.'
                ])
                add(fam, action, target('DONE'))
            elif typ == 'CHECK':
                attr, goal = rng.choice(CHECKS); dc = rng.randint(10,18)
                add(fam, f'Я пытаюсь {goal}.', target('CHECK', attr, str(dc), f'Проверка: {goal}.'))
            elif typ == 'INV_ADD':
                add(fam, f'Я беру предмет «{item}» и оставляю его себе.', target(typ, item, '', f'Получен предмет: {item}.'))
            elif typ == 'INV_REMOVE':
                st['inventory'] = list(dict.fromkeys(st['inventory'] + [item]))
                add(fam, f'Я выбрасываю предмет «{item}» и ухожу без него.', target(typ, item, '', f'Потерян предмет: {item}.'), state=st)
            elif typ == 'HP':
                delta = rng.choice([-5,-4,-3,-2,2,3,4])
                add(fam, f'Подтверждённое последствие уже произошло: герой получает изменение здоровья {delta:+d}.', target('HP','PLAYER',f'{delta:+d}','Изменение здоровья подтверждено.'), state=st)
            elif typ == 'MONEY':
                delta = rng.choice([-20,-10,-5,5,10,20])
                add(fam, f'Сделка завершена, количество монет героя меняется на {delta:+d}.', target('MONEY','PLAYER',f'{delta:+d}','Изменение денег подтверждено.'), state=st)
            elif typ == 'NPC_UPSERT':
                add(fam, f'В зал впервые входит {role} {npc}, называет своё имя и остаётся рядом.', target(typ,npc,'',f'Появился новый NPC: {npc}, {role}.'))
            elif typ == 'NPC_MEMORY':
                st['npcs'] = [f'{npc} | ACTIVE | HP 10/10 | {st["location"]} | Разговаривает с героем.']
                val = rng.choice(['GOOD','BAD','NEUTRAL'])
                add(fam, f'{npc} запоминает поступок героя и теперь относится к нему как {val}.', target(typ,npc,val,f'{npc} запомнил поступок героя.'), state=st)
            elif typ == 'NPC_STATUS':
                st['npcs'] = [f'{npc} | ACTIVE | HP 10/10 | {st["location"]} | Разговаривает с героем.']
                val = rng.choice(['ALLY','HOSTILE','MISSING','INACTIVE','KNOWN'])
                add(fam, f'После произошедшего статус NPC {npc} подтверждён как {val}.', target(typ,npc,val,f'Статус {npc} изменён на {val}.'), state=st)
            elif typ == 'WORLD_ADD':
                add(fam, f'Событие «{event}» действительно начинается и надолго меняет регион.', target(typ,event,str(rng.randint(1,3)),'Подтверждённое долгосрочное изменение мира.'))
            elif typ == 'WORLD_UPDATE':
                st['world_events'] = [f'{event} | ACTIVE | IMPORTANCE 2 | Событие продолжается.']
                add(fam, f'Для события «{event}» появилось новое подтверждённое обстоятельство.', target(typ,event,'2','Появилось новое подтверждённое обстоятельство.'), state=st)
            elif typ == 'WORLD_RESOLVE':
                st['world_events'] = [f'{event} | ACTIVE | IMPORTANCE 2 | Событие продолжается.']
                add(fam, f'Причина события «{event}» устранена; событие завершилось.', target(typ,event,'','Событие завершено.'), state=st)
            elif typ == 'QUEST_START':
                add(fam, f'Заказчик официально предлагает задание «{quest}», и герой принимает его.', target(typ,quest,'','Новое задание принято.'))
            elif typ == 'QUEST_UPDATE':
                st['quests'] = [f'{quest} | ACTIVE | Выполнить поручение.']
                add(fam, f'По заданию «{quest}» найдена новая важная улика, но оно не завершено.', target(typ,quest,'','Найдена новая важная улика.'), state=st)
            elif typ == 'QUEST_COMPLETE':
                st['quests'] = [f'{quest} | ACTIVE | Выполнить поручение.']
                add(fam, f'Цель задания «{quest}» выполнена и заказчик подтверждает успех.', target(typ,quest,'','Задание выполнено.'), state=st)
            elif typ == 'QUEST_FAIL':
                st['quests'] = [f'{quest} | ACTIVE | Выполнить поручение.']
                add(fam, f'Цель задания «{quest}» стала окончательно недостижима.', target(typ,quest,'','Задание провалено.'), state=st)
            elif typ == 'ABILITY_ADD':
                add(fam, f'После завершённого обучения герой осваивает способность «{ability}».', target(typ,ability,ability_kind,f'Освоена способность: {ability}.'))
            elif typ == 'ABILITY_UPDATE':
                st['abilities'] = [f'{ability} | {ability_kind}']
                new_kind = rng.choice(['SKILL','SPELL','TRAIT','POWER'])
                add(fam, f'Способность «{ability}» подтверждённо меняет категорию на {new_kind}.', target(typ,ability,new_kind,f'Способность обновлена: {ability}.'), state=st)
            elif typ == 'ABILITY_REMOVE':
                st['abilities'] = [f'{ability} | {ability_kind}']
                add(fam, f'Герой окончательно утрачивает способность «{ability}».', target(typ,ability,'',f'Утрачена способность: {ability}.'), state=st)
            elif typ == 'EFFECT_ADD':
                add(fam, f'На героя действительно накладывается состояние «{effect}».', target(typ,effect,'',f'Добавлен эффект: {effect}.'))
            elif typ == 'EFFECT_REMOVE':
                st['effects'] = [effect]
                add(fam, f'Состояние «{effect}» полностью снимается с героя.', target(typ,effect,'',f'Снят эффект: {effect}.'), state=st)
            elif typ == 'LOCATION':
                add(fam, f'Я прохожу безопасным путём и достигаю локации «{loc}».', target(typ,loc,'',f'Герой вошёл в локацию «{loc}».'))

    # CHECK_RESULT: deliberate physical/non-physical failures.
    for i in range(max(500, count // 20)):
        fam = f'v4_check_result_{i:05d}'
        attr, goal = rng.choice(CHECKS)
        physical = i % 2 == 0
        check = {'attribute': attr, 'reason': goal, 'dc': rng.randint(10,18), 'roll_total': rng.randint(1,9)}
        tgt = target('HP','PLAYER',str(rng.choice([-2,-3,-4])),f'Провал: {goal}.') if physical else target('DONE')
        add(fam, 'Результат проверки уже определён.', tgt, mode='CHECK_RESULT', check=check)

    rng.shuffle(rows)
    return rows[:count]


NARRATOR_SYSTEM = '<MODE_NARRATOR>\nТы мастер мрачной RPG. Продолжи сцену кратко, атмосферно и конкретно. Не решай за игрока. Не печатай tool-call.'


def make_narrative(count: int, rng: random.Random) -> list[dict]:
    """Build three natural variants per semantic family with unique answers.

    The family split prevents close variants from leaking between train and eval.
    Every assistant answer contains a family-specific natural detail and is checked
    for exact uniqueness before the pack is written.
    """
    rows: list[dict] = []
    family_count = (count + 2) // 3
    sensory = [
        ('ветер', 'ржавые цепи', 'сухим железом'),
        ('дождь', 'битая черепица', 'мокрым камнем'),
        ('вода', 'каменные плиты', 'сырой глиной'),
        ('туман', 'чёрные ели', 'холодной хвоей'),
        ('дым', 'пустые прилавки', 'горелым маслом'),
        ('эхо', 'рубленый камень', 'пылью и известью'),
        ('снег', 'старые колеи', 'морозной землёй'),
        ('шёпот листвы', 'низкая ограда', 'прелыми листьями'),
        ('гул печи', 'закопчённые балки', 'углём'),
        ('плеск реки', 'скользкие валуны', 'речной тиной'),
    ]
    actions = [
        'Я медленно осматриваюсь, ничего не трогая.',
        'Я замираю и прислушиваюсь.',
        'Я спрашиваю {npc}, что здесь произошло.',
        'Я осторожно делаю шаг к дальней стене.',
        'Я останавливаюсь у закрытой двери и изучаю её.',
        'Я кладу предмет «{item}» на видное место и отступаю.',
        'Проверка уже завершилась успехом: я замечаю скрытый след.',
        'Проверка уже завершилась неудачей, но прямой травмы нет.',
        'Я спокойно перехожу в следующую часть помещения.',
        'Я ничего не предпринимаю и наблюдаю за реакцией собеседника.',
    ]

    for family_index in range(family_count):
        family = f'v4n_{family_index:06d}'
        loc = LOCATIONS[family_index % len(LOCATIONS)]
        npc = NAMES[(family_index * 5 + 3) % len(NAMES)]
        item = ITEMS[(family_index * 7 + 1) % len(ITEMS)]
        sound, landmark, smell = sensory[(family_index * 3 + 2) % len(sensory)]
        detail = natural_detail(family_index)
        action_template = actions[family_index % len(actions)]
        action = action_template.format(npc=npc, item=item)
        scene = (
            f'Локация «{loc}» погружена в полумрак. Слышен {sound}; рядом видны {landmark}. '
            f'Воздух пахнет {smell}. {npc} следит за героем. На краю света лежит {item}. '
            f'У дальней стены находится {detail}.'
        )

        category = family_index % 10
        if category == 0:  # exploration
            answers = [
                f'Осмотр не нарушает тишины. Возле {detail} пыль сметена узкой полосой, ведущей к {landmark}. {npc} замечает след одновременно с героем и переводит взгляд на {item}.',
                f'{sound.capitalize()} на миг стихает. Под предметом «{detail}» обнаруживается свежая царапина, а рядом — отпечаток подошвы; {npc} молча отступает от {landmark}.',
                f'В привычной картине выделяется {detail}: его недавно сдвигали, хотя вокруг всё покрыто старой пылью. От него тянется едва заметный след к месту, где лежит {item}.',
            ]
        elif category == 1:  # listening
            answers = [
                f'Сначала слышен только {sound}. Затем за {landmark} один раз скрипит доска, а {detail} едва заметно дрожит, будто рядом кто-то задержал дыхание.',
                f'Тишина постепенно разделяется на отдельные звуки. Из-за {landmark} доносится короткий вдох; {npc} смотрит на {detail}, но не произносит ни слова.',
                f'Через несколько секунд возле предмета «{detail}» раздаётся тихий щелчок. {sound.capitalize()} его почти скрывает, однако движение за {landmark} повторяется.',
            ]
        elif category == 2:  # dialogue
            answers = [
                f'{npc} отвечает после долгой паузы: — До рассвета здесь был ещё один человек. — Собеседник кивает на {detail}, где остался след свежей грязи, и избегает смотреть на {item}.',
                f'— Я пришёл уже после шума, — негромко говорит {npc}. Его взгляд задерживается на {landmark}, затем на предмете «{detail}»; последнее слово звучит слишком поспешно.',
                f'{npc} проводит пальцем по краю предмета «{detail}». — Кто-то искал {item}, — говорит он. — И, похоже, не нашёл. За его спиной по-прежнему слышен {sound}.',
            ]
        elif category == 3:  # advance
            answers = [
                f'Шаг отзывается глухим эхом. У {landmark} обнаруживается {detail}, а за ним — узкий проход, откуда тянет запахом {smell}; {npc} остаётся позади.',
                f'По мере приближения становится видно, что {detail} закрывает часть старой надписи. {sound.capitalize()} усиливается, и возле {landmark} проступает тёмная щель.',
                f'Дальняя стена оказывается не сплошной: рядом с предметом «{detail}» заметен вертикальный шов. {npc} следит за ним, пока герой приближается к {landmark}.',
            ]
        elif category == 4:  # door
            answers = [
                f'Дверь холодна и не поддаётся от лёгкого касания. Рядом закреплён {detail}; на его поверхности видна свежая потёртость, а из-за створки доносится {sound}.',
                f'На замке нет следов взлома, зато у порога стоит {detail}, недавно передвинутый к {landmark}. {npc} замечает тонкую нить, уходящую под дверь.',
                f'Между досками тянет воздухом, пахнущим {smell}. Предмет «{detail}» заслоняет нижнюю петлю, и возле неё виден след свежего масла.',
            ]
        elif category == 5:  # placed item
            answers = [
                f'{item.capitalize()} остаётся на виду рядом с предметом «{detail}». Несколько мгновений ничего не происходит, затем за {landmark} прекращается движение, и {npc} настораживается.',
                f'Слабый свет цепляется за {item}. {sound.capitalize()} продолжается, но возле {detail} появляется тень, которой прежде не было; {npc} медленно поворачивает голову.',
                f'Оставленный {item} выглядит намеренным знаком. У {landmark} раздаётся тихий шорох, а предмет «{detail}» чуть сдвигается, хотя к нему никто не подходит.',
            ]
        elif category == 6:  # successful check
            answers = [
                f'Скрытый след становится очевиден: от {detail} к {landmark} тянется цепочка мелких капель. {npc} замечает её лишь после того, как взгляд останавливается на {item}.',
                f'Под слоем пыли возле предмета «{detail}» проступает знак, повторённый на краю {item}. След уходит за {landmark}, где недавно кто-то стоял.',
                f'Внимательность связывает детали воедино. {sound.capitalize()} маскировал лёгкий скрежет, а {detail} скрывает свежий отпечаток пальцев, направленный к {landmark}.',
            ]
        elif category == 7:  # failed check, no invented damage
            answers = [
                f'Осмотр не даёт уверенного ответа. {detail.capitalize()} остаётся единственной необычной деталью, но {sound} и движение теней мешают понять, связан ли он с {item}.',
                f'Ни у {landmark}, ни возле предмета «{detail}» не находится надёжного следа. {npc} ждёт ответа, пока запах {smell} становится только сильнее.',
                f'Попытка разобраться заканчивается сомнением: {item} выглядит обычным, а {detail} мог оказаться здесь давно. За {landmark} по-прежнему слышен лишь {sound}.',
            ]
        elif category == 8:  # safe transition
            answers = [
                f'Переход проходит без происшествий. За {landmark} открывается продолжение локации «{loc}», где первым ориентиром становится {detail}; {sound} остаётся позади.',
                f'Коридор выводит в более просторную часть помещения. У стены стоит {detail}, рядом лежит {item}, а {npc} останавливается у границы света.',
                f'Через несколько шагов прежний проход остаётся позади. В новом участке «{loc}» слышен запах {smell}; возле {landmark} виден предмет «{detail}».',
            ]
        else:  # observation without deciding for player
            answers = [
                f'{npc} первым отводит взгляд. Рядом с {landmark} остаётся {detail}, а {item} лежит нетронутым; {sound} заполняет паузу между собеседниками.',
                f'Наблюдение затягивается. {npc} несколько раз смотрит на предмет «{detail}», словно ждёт вопроса, но не приближается ни к нему, ни к {item}.',
                f'Никто не делает первого движения. Только {sound} и слабый запах {smell} нарушают тишину; у {landmark} по-прежнему виден {detail}.',
            ]

        for variant_index, answer in enumerate(answers):
            if len(rows) >= count:
                break
            rows.append({
                'id': f'v4n_{len(rows)+1:06d}',
                'kind': 'NARRATIVE',
                'family': family,
                'split': split_for(family),
                'expected': {'kind': 'NARRATIVE', 'anchors': [npc, item, detail]},
                'messages': [
                    {'role': 'system', 'content': NARRATOR_SYSTEM},
                    {'role': 'user', 'content': f'CURRENT_SCENE:\n{scene}\n\nLOCATION:\n{loc}\n\nPLAYER_ACTION:\n{action}'},
                    {'role': 'assistant', 'content': answer},
                ],
            })

    outputs = [row['messages'][-1]['content'].strip() for row in rows]
    if len(outputs) != len(set(outputs)):
        duplicates = len(outputs) - len(set(outputs))
        raise RuntimeError(f'narrative generator produced {duplicates} duplicate answers')
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description='Generate a large deterministic MyDND v4 dataset.')
    p.add_argument('--director', type=int, default=24000)
    p.add_argument('--narrative', type=int, default=6000)
    p.add_argument('--seed', type=int, default=SEED)
    p.add_argument('--prefix', default='v4_mass')
    args = p.parse_args()
    if args.director < 2200:
        raise SystemExit('--director must be >= 2200 to cover all action types')
    rng = random.Random(args.seed)
    director = make_director(args.director, rng)
    narrative = make_narrative(args.narrative, rng)
    narrative_unique = len({r['messages'][-1]['content'].strip() for r in narrative})
    if narrative_unique != len(narrative):
        raise RuntimeError(f'narrative uniqueness check failed: {narrative_unique}/{len(narrative)}')
    dpath = PACKS / f'{args.prefix}_director.jsonl'
    npath = PACKS / f'{args.prefix}_narrative.jsonl'
    write_jsonl(dpath, director)
    write_jsonl(npath, narrative)
    counts = Counter(r['target']['type'] for r in director)
    print(f'Wrote {len(director)} Director rows -> {dpath}')
    print(f'Wrote {len(narrative)} Narrative rows -> {npath}')
    print(f'Narrative unique answers: {narrative_unique}/{len(narrative)} (100.0%)')
    print('Director distribution:')
    for typ in DIRECTOR_TYPES:
        print(f'  {typ:16s} {counts[typ]:6d}')
    print('Next: ./mydnd.sh prepare && ./mydnd.sh audit')


if __name__ == '__main__':
    main()
