# Добавление dataset packs

## Принцип

Каждый набор — отдельный `datasets/packs/*.jsonl`. Команда `prepare_dataset.py` автоматически объединяет все pack-файлы, валидирует контракт и создаёт:

```text
datasets/compiled/train.jsonl
datasets/compiled/director_eval.jsonl
datasets/compiled/narrative_eval.jsonl
datasets/compiled/manifest.json
```

Compiled-файлы не коммитятся: они воспроизводимо собираются из packs.

## Family и split

Похожие варианты одного сценария должны иметь одинаковый `family`. Это защищает от попадания почти одинаковых примеров одновременно в train и eval.

Можно указать:

```json
"split": "auto"
```

Тогда split детерминированно вычислится по `family`. Все строки одной семьи попадут в одну часть.

## Director row

```json
{
  "id": "inventory_v4_0001",
  "kind": "DIRECTOR",
  "family": "inventory_take_free_item_001",
  "split": "auto",
  "mode": "PLAYER_ACTION",
  "current_scene": "На столе лежит ржавый ключ.",
  "world": "Мрачное пограничье.",
  "character": "Путник.",
  "summary": "",
  "recent_events": [],
  "relevant_facts": [],
  "active_situations": "",
  "state": {
    "location": "Караульная",
    "hp": "12/12",
    "money": "8",
    "inventory": [],
    "npcs": [],
    "quests": [],
    "world_events": [],
    "abilities": [],
    "effects": [],
    "action_hint": "NONE"
  },
  "player_action": "Я беру ржавый ключ со стола и оставляю себе.",
  "target": {
    "type": "INV_ADD",
    "name": "Ржавый ключ",
    "value": "",
    "details": "Ржавый ключ получен."
  }
}
```

## Narrative row

```json
{
  "id": "narrator_v4_0001",
  "kind": "NARRATIVE",
  "family": "narrator_door_listen_001",
  "split": "auto",
  "expected": {
    "kind": "NARRATIVE",
    "anchors": ["дверь", "холод"]
  },
  "messages": [
    {
      "role": "system",
      "content": "<MODE_NARRATOR>\nТы мастер мрачной RPG. Не решай за игрока."
    },
    {
      "role": "user",
      "content": "CURRENT_SCENE:\nВ стене видна старая дверь.\n\nPLAYER_ACTION:\nЯ прислушиваюсь."
    },
    {
      "role": "assistant",
      "content": "За дверью один раз скрипит доска, затем всё стихает. Из щели тянет холодным воздухом."
    }
  ]
}
```

## Правила качества

- Не копировать один ответ десятки раз.
- Делать контрастные семьи: намерение / попытка / завершённое действие / отсутствие изменения.
- В Narrative использовать конкретные детали входной сцены.
- Не включать в eval вручную перефразированные копии train; объединять их одним `family`.
- Не придумывать action type, которого нет в Java-контракте.
- После добавления всегда выполнять `./mydnd.sh prepare` и `./mydnd.sh audit`.
