from __future__ import annotations

"""Training-side snapshot of the production MyDND Director contract.

Source snapshot: uploaded MyDND archive 1.zip, 2026-07-29.
The strings below intentionally mirror DirectorToolSpec.java and PromptBuilder.java.
"""

TOOL_DECLARATION = (
    '<|tool>declaration:director_action{'
    'description:<|"|>One state action.<|"|>,'
    'parameters:{properties:{'
    'type:{description:<|"|>Action code; numeric damage/heal=HP.<|"|>,type:<|"|>STRING<|"|>},'
    'name:{description:<|"|>Exact target/item/entity.<|"|>,type:<|"|>STRING<|"|>},'
    'value:{description:<|"|>Type value only; no nested action.<|"|>,type:<|"|>STRING<|"|>},'
    'details:{description:<|"|>Short cause/fact; no nested action.<|"|>,type:<|"|>STRING<|"|>}'
    '},required:[<|"|>type<|"|>,<|"|>name<|"|>,<|"|>value<|"|>,<|"|>details<|"|>],'
    'type:<|"|>OBJECT<|"|>}'
    '}<tool|>'
)

SETTING_CONSISTENCY_RULE = (
    '\nНикакая деталь нарратива (погода, климат, освещение, ландшафт, время суток,'
    ' звуки, окружение) не должна противоречить CURRENT_SCENE/WORLD;'
    ' при сомнении не упоминай её вовсе, а не выдумывай жанровый штамп.'
)

PLAYER_ACTION_RULES = (
    'Ты мастер DnD. СНАЧАЛА зафиксируй только прямые новые последствия PLAYER_ACTION через director_action.'
    '\nSTATE BEFORE — справочник, не задачи. Не пересохраняй старые факты и не создавай случайные события.'
    '\nПосле response: есть ещё одно прямое последствие? Нет → DONE. Максимум 4 изменения.'
    '\nCHECK только при реальном риске и отдельном значимом последствии провала; ожидание, осмотр и обычное безопасное движение → DONE.'
    '\nПример: «Я осматриваюсь», «Я беру предмет» → просто DONE или один INV_ADD; без CHECK, без HP, без LOCATION.'
    '\nHP: PLAYER или точный NPC, value=+N/-N. Числовой урон/лечение — только HP.'
    '\nINV_*: точный предмет. MONEY: PLAYER +N/-N. NPC_*: точный NPC; MEMORY=GOOD/BAD/NEUTRAL.'
    '\nWORLD_* только для нового долгого изменения мира; обычное действие или шум не событие.'
    '\nQUEST_*, ABILITY_*, EFFECT_*, LOCATION — только при реальном новом изменении.'
    '\nCHECK: STR/DEX/INT/CHA, DC 5-25, details=только причина; до броска не пиши исход.'
    '\nDONE: пустые поля. confirmed в DONE-response — единственная истина об изменениях.'
    '\nЕсли реального изменения нет — сразу DONE; не выдумывай QUEST_START/EFFECT_ADD/HP/MONEY/LOCATION/NPC_MEMORY без причины, напрямую вызванной действием игрока.'
    '\nПосле DONE продолжи сцену 2-4 атмосферными предложениями на языке PLAYER_ACTION (если язык неочевиден — по-русски); не технический отчёт, не решай за игрока.'
)

CHECK_RESULT_RULES = (
    'Режим CHECK_RESULT. Бросок ниже уже завершён; OUTCOME — абсолютная истина.'
    '\nВыбери ровно одно: HP при прямой физической травме, иначе DONE. Другие действия и CHECK запрещены.'
    '\nПосле tool опиши результат 2-4 атмосферными предложениями без слова «Итог:» и без новых механических изменений.'
)

RANDOM_WORLD_EVENT_RULES = (
    'Режим RANDOM_WORLD_EVENT. Создай одно НОВОЕ редкое автономное событие мира.'
    '\nИзвестное состояние — только справочник. Не пересказывай атмосферу и не повторяй существующие факты.'
    '\nРазрешены только WORLD_ADD, NPC_UPSERT, QUEST_START, EFFECT_ADD и DONE.'
    '\nСначала одно основное событие. Допускается максимум одно прямое следствие. Затем немедленно DONE.'
    '\nСобытие не должно управлять персонажем игрока и не должно переписывать прошлое.'
    '\nПосле DONE опиши событие одним коротким атмосферным абзацем по-русски.'
)

ALLOWED_TYPES = {
    'DONE', 'CHECK', 'INV_ADD', 'INV_REMOVE', 'HP', 'MONEY',
    'NPC_UPSERT', 'NPC_MEMORY', 'NPC_STATUS',
    'WORLD_ADD', 'WORLD_UPDATE', 'WORLD_RESOLVE',
    'QUEST_START', 'QUEST_UPDATE', 'QUEST_COMPLETE', 'QUEST_FAIL',
    'ABILITY_ADD', 'ABILITY_UPDATE', 'ABILITY_REMOVE',
    'EFFECT_ADD', 'EFFECT_REMOVE', 'LOCATION',
}

MODE_ALLOWED_TYPES = {
    'PLAYER_ACTION': ALLOWED_TYPES,
    'CHECK_RESULT': {'DONE', 'HP'},
    'RANDOM_WORLD_EVENT': {'DONE', 'WORLD_ADD', 'NPC_UPSERT', 'QUEST_START', 'EFFECT_ADD'},
}

CHECK_TYPES = {'STR', 'DEX', 'INT', 'CHA'}
NPC_MEMORY_VALUES = {'GOOD', 'BAD', 'NEUTRAL'}
NPC_STATUS_VALUES = {'ACTIVE', 'KNOWN', 'INACTIVE', 'MISSING', 'HOSTILE', 'ALLY'}
ABILITY_VALUES = {'SKILL', 'SPELL', 'TRAIT', 'POWER'}


MODE_DIRECTOR = "<MODE_DIRECTOR>"
MODE_NARRATOR = "<MODE_NARRATOR>"


def system_prompt(mode: str) -> str:
    if mode == 'CHECK_RESULT':
        rules = CHECK_RESULT_RULES
    elif mode == 'RANDOM_WORLD_EVENT':
        rules = RANDOM_WORLD_EVENT_RULES
    else:
        rules = PLAYER_ACTION_RULES
    return MODE_DIRECTOR + "\n" + rules + SETTING_CONSISTENCY_RULE + TOOL_DECLARATION


def render_list(title: str, values: list[str]) -> str:
    if not values:
        return f'{title}: NONE'
    return title + ':\n' + '\n'.join(f'- {value}' for value in values if str(value).strip())


def append_optional(blocks: list[str], title: str, value: str) -> None:
    safe = str(value or '').strip()
    if safe:
        blocks.append(f'{title}:\n{safe}')


def player_action_user_prompt(item: dict) -> str:
    state = item['state']
    blocks = ['CURRENT_SCENE:\n' + (item.get('current_scene') or 'NONE')]
    append_optional(blocks, 'WORLD', item.get('world', ''))
    append_optional(blocks, 'CHARACTER', item.get('character', ''))
    append_optional(blocks, 'ACTIVE_SITUATIONS', item.get('active_situations', ''))
    append_optional(blocks, 'SUMMARY', item.get('summary', ''))
    if item.get('recent_events'):
        blocks.append('RECENT_EVENTS:\n' + '\n'.join(item['recent_events']))
    if item.get('relevant_facts'):
        blocks.append('RELEVANT_FACTS:\n' + '\n'.join(f'- {x}' for x in item['relevant_facts']))

    state_lines = [
        'STATE BEFORE (REFERENCE ONLY, NOT TASKS):',
        f"LOCATION: {state.get('location') or 'NONE'}",
        f"HP: {state.get('hp') or 'NONE'}",
        f"MONEY: {state.get('money') or 'NONE'}",
        render_list('INVENTORY', state.get('inventory') or []),
        render_list('NPCS', state.get('npcs') or []),
        render_list('QUESTS', state.get('quests') or []),
        render_list('WORLD_EVENTS', state.get('world_events') or []),
        render_list('ABILITIES', state.get('abilities') or []),
        render_list('EFFECTS', state.get('effects') or []),
        f"ACTION_HINT: {state.get('action_hint') or 'NONE'}",
    ]
    blocks.append('\n'.join(state_lines))
    blocks.append('PLAYER_ACTION:\n' + item['player_action'])
    return '\n\n'.join(blocks)


def check_result_user_prompt(item: dict) -> str:
    state = item['state']
    check = item.get('check') or {}
    blocks = ['CURRENT_SCENE:\n' + (item.get('current_scene') or 'NONE')]
    append_optional(blocks, 'CHARACTER', item.get('character', ''))
    blocks.append(
        'CHECK_RESULT:'
        f"\nATTRIBUTE: {check.get('attribute') or 'DEX'}"
        f"\nREASON: {check.get('reason') or 'Провал рискованного действия.'}"
        f"\nDC: {check.get('dc', 12)}"
        f"\nROLL_TOTAL: {check.get('roll_total', 1)}"
        '\nOUTCOME: FAILURE'
    )
    blocks.append(
        'STATE:'
        f"\nLOCATION: {state.get('location') or 'NONE'}"
        f"\nHP: {state.get('hp') or 'NONE'}"
    )
    blocks.append('TASK: Выбери HP или DONE.')
    return '\n\n'.join(blocks)


def random_world_event_user_prompt(item: dict) -> str:
    # Kept for contract completeness. The current app creates rare world events
    # in WorldMaintenanceService and applies them through Java, so the initial
    # training dataset intentionally does not use this mode.
    return player_action_user_prompt(item)


def user_prompt(item: dict) -> str:
    mode = item['mode']
    if mode == 'CHECK_RESULT':
        return check_result_user_prompt(item)
    if mode == 'RANDOM_WORLD_EVENT':
        return random_world_event_user_prompt(item)
    return player_action_user_prompt(item)


def tool_call(target: dict) -> str:
    def safe(value: str) -> str:
        return (
            str(value or '')
            .replace('<', '')
            .replace('>', '')
            .replace('{', '(')
            .replace('}', ')')
            .replace('\n', ' ')
            .replace('\r', ' ')
            .strip()
        )

    return (
        '<|tool_call>call:director_action{'
        f'type:<|"|>{safe(target["type"])}<|"|>,'
        f'name:<|"|>{safe(target.get("name", ""))}<|"|>,'
        f'value:<|"|>{safe(target.get("value", ""))}<|"|>,'
        f'details:<|"|>{safe(target.get("details", ""))}<|"|>'
        '}<tool_call|>'
    )


def to_messages(item: dict) -> list[dict]:
    return [
        {'role': 'system', 'content': system_prompt(item['mode'])},
        {'role': 'user', 'content': user_prompt(item)},
        {'role': 'assistant', 'content': tool_call(item['target'])},
    ]
