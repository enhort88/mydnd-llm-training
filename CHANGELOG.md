# Changelog

## v3

- Проект перестроен под постоянный Git-репозиторий.
- Dataset разбит на независимые `datasets/packs/*.jsonl`.
- Добавлена автоматическая компиляция и детерминированный split по `family`.
- Добавлены 480 hard Director-примеров.
- Добавлены 360 уникальных Narrative-примеров без дословных повторов.
- Удалены повторяющиеся Narrative anchors v2.
- Добавлены `<MODE_DIRECTOR>` и `<MODE_NARRATOR>`.
- Learning rate по умолчанию снижен с `7e-5` до `4e-5`.
- Добавлены метрики `unique_output_rate` и `anchor_hit_rate` рассказчика.
- Добавлена постоянная локальная папка модели и offline-режим.
- Добавлен единый launcher `mydnd.sh`.
