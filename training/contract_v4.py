from __future__ import annotations

"""Compact v4 training contract.

This prompt is intentionally much shorter than v3. Android must later mirror the
same labels and rules before the v4 adapter is shipped.
"""

TOOL_DECLARATION = (
    '<|tool>declaration:director_action{'
    'description:<|"|>One direct state action.<|"|>,'
    'parameters:{properties:{'
    'type:{description:<|"|>Action code.<|"|>,type:<|"|>STRING<|"|>},'
    'name:{description:<|"|>Exact target.<|"|>,type:<|"|>STRING<|"|>},'
    'value:{description:<|"|>Type value.<|"|>,type:<|"|>STRING<|"|>},'
    'details:{description:<|"|>Short confirmed cause or fact.<|"|>,type:<|"|>STRING<|"|>}'
    '},required:[<|"|>type<|"|>,<|"|>name<|"|>,<|"|>value<|"|>,<|"|>details<|"|>],'
    'type:<|"|>OBJECT<|"|>}'
    '}<tool|>'
)

MODE_DIRECTOR = '<MODE_DIRECTOR>'
MODE_NARRATOR = '<MODE_NARRATOR>'

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

PLAYER_ACTION_RULES = (
    'Return one direct NEW state consequence of ACTION. STATE is reference, never a task. '
    'No real change => DONE. Real risk with a meaningful failure => CHECK. '
    'Never invent, repeat, or save atmosphere as state. Use exact entity names. '
    'After an applied tool response, return the next direct consequence or DONE; max 4 applied actions.\n'
    'Codes: DONE CHECK INV_ADD INV_REMOVE HP MONEY NPC_UPSERT NPC_MEMORY NPC_STATUS '
    'WORLD_ADD WORLD_UPDATE WORLD_RESOLVE QUEST_START QUEST_UPDATE QUEST_COMPLETE QUEST_FAIL '
    'ABILITY_ADD ABILITY_UPDATE ABILITY_REMOVE EFFECT_ADD EFFECT_REMOVE LOCATION.\n'
    'Fields: DONE=all empty; CHECK name=STR|DEX|INT|CHA value=DC 5..25; '
    'HP/MONEY value=+N|-N; MONEY name=PLAYER; NPC_MEMORY=GOOD|BAD|NEUTRAL; '
    'WORLD importance=1..3; abilities=SKILL|SPELL|TRAIT|POWER. '
    'Do not decide the player action or contradict SCENE/WORLD.'
)

CHECK_RESULT_RULES = (
    'CHECK_RESULT is final. Return HP only for direct physical injury; otherwise DONE. '
    'No CHECK and no other action. Do not invent extra consequences.'
)

RANDOM_WORLD_EVENT_RULES = (
    'Create one rare NEW autonomous world event. Allowed: WORLD_ADD, NPC_UPSERT, '
    'QUEST_START, EFFECT_ADD, DONE. Do not repeat known state or control the player.'
)

NARRATOR_SYSTEM_PROMPT = (
    MODE_NARRATOR + '\n'
    'Continue the current scene in Russian with 2-4 concise atmospheric sentences. '
    'Use only given facts and confirmed changes. Never choose actions for the player, '
    'print tools, add mechanics, or contradict the setting.'
)


def system_prompt(mode: str) -> str:
    if mode == 'CHECK_RESULT':
        rules = CHECK_RESULT_RULES
    elif mode == 'RANDOM_WORLD_EVENT':
        rules = RANDOM_WORLD_EVENT_RULES
    else:
        rules = PLAYER_ACTION_RULES
    return MODE_DIRECTOR + '\n' + rules + '\n' + TOOL_DECLARATION


def clean(value: object) -> str:
    return str(value or '').strip()


def compact_list(values: list[str]) -> str:
    return '; '.join(clean(v) for v in values if clean(v))


def add(blocks: list[str], label: str, value: object) -> None:
    text = clean(value)
    if text:
        blocks.append(f'{label}: {text}')


def player_action_user_prompt(item: dict) -> str:
    state = item['state']
    blocks: list[str] = []
    add(blocks, 'SCENE', item.get('current_scene'))
    add(blocks, 'WORLD', item.get('world'))
    add(blocks, 'PC', item.get('character'))
    add(blocks, 'SITUATIONS', item.get('active_situations'))
    add(blocks, 'SUMMARY', item.get('summary'))
    if item.get('recent_events'):
        add(blocks, 'RECENT', ' | '.join(clean(x) for x in item['recent_events'] if clean(x)))
    if item.get('relevant_facts'):
        add(blocks, 'FACTS', ' | '.join(clean(x) for x in item['relevant_facts'] if clean(x)))

    core = []
    if clean(state.get('location')):
        core.append('LOC=' + clean(state.get('location')))
    if clean(state.get('hp')):
        core.append('HP=' + clean(state.get('hp')))
    if clean(state.get('money')):
        core.append('MONEY=' + clean(state.get('money')))
    if core:
        blocks.append('STATE: ' + ' | '.join(core))

    for label, key in (
        ('INV', 'inventory'), ('NPC', 'npcs'), ('QUEST', 'quests'),
        ('WORLD_EVENTS', 'world_events'), ('ABILITY', 'abilities'), ('EFFECT', 'effects'),
    ):
        values = state.get(key) or []
        text = compact_list(values)
        if text:
            blocks.append(f'{label}: {text}')

    hint = clean(state.get('action_hint'))
    if hint and hint != 'NONE':
        blocks.append('HINT: ' + hint)
    blocks.append('ACTION: ' + clean(item.get('player_action')))
    return '\n'.join(blocks)


def check_result_user_prompt(item: dict) -> str:
    state = item['state']
    check = item.get('check') or {}
    blocks = []
    add(blocks, 'SCENE', item.get('current_scene'))
    add(blocks, 'PC', item.get('character'))
    blocks.append(
        'CHECK_RESULT: '
        f"{clean(check.get('attribute')) or 'DEX'} | reason={clean(check.get('reason')) or 'failure'} | "
        f"DC={check.get('dc', 12)} | roll={check.get('roll_total', 1)} | outcome=FAILURE"
    )
    blocks.append(
        f"STATE: LOC={clean(state.get('location')) or 'NONE'} | HP={clean(state.get('hp')) or 'NONE'}"
    )
    return '\n'.join(blocks)


def random_world_event_user_prompt(item: dict) -> str:
    return player_action_user_prompt(item)


def user_prompt(item: dict) -> str:
    mode = item['mode']
    if mode == 'CHECK_RESULT':
        return check_result_user_prompt(item)
    if mode == 'RANDOM_WORLD_EVENT':
        return random_world_event_user_prompt(item)
    return player_action_user_prompt(item)


def tool_call(target: dict) -> str:
    def safe(value: object) -> str:
        return (
            clean(value)
            .replace('<', '')
            .replace('>', '')
            .replace('{', '(')
            .replace('}', ')')
            .replace('\n', ' ')
            .replace('\r', ' ')
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
