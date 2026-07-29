# MyDND LLM Training

Постоянный Git-проект для QLoRA-дообучения локальной Gemma 4 под MyDND.

Проект больше не нужно получать новыми архивами после каждого изменения. Скрипты, конфигурация и JSONL-наборы хранятся в Git. Новые данные добавляются отдельными файлами в `datasets/packs/`, после чего выполняется `./mydnd.sh prepare`.

## Что хранится и что не хранится в Git

В Git:

- обучающие скрипты;
- конфигурация эксперимента;
- небольшие JSONL dataset packs;
- валидаторы и тесты;
- описание контрактов Director/Narrator.

Не в Git:

- `.venv`;
- базовая Gemma;
- Hugging Face cache;
- LoRA-адаптеры;
- GGUF;
- логи и отчёты.

Это уже прописано в `.gitignore`.

## Модель не скачивается каждый раз

Обычный запуск с Hub ID уже повторно использует `~/.cache/huggingface/hub`. Новая папка проекта не означает новую загрузку модели.

Для полностью стабильного локального пути один раз выполни:

```bash
./mydnd.sh model-cache
```

Модель окажется в:

```text
~/Models/MyDND/gemma-4-E2B-training
```

После этого `train_qlora.py` автоматически выбирает локальную папку. Для жёсткого офлайн-режима:

```bash
export MYDND_BASE_MODEL="$HOME/Models/MyDND/gemma-4-E2B-training"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

## Текущий dataset v3

После компиляции:

- 1 880 записей;
- 1 520 Director-примеров;
- 360 уникальных Narrative-примеров;
- 1 504 train;
- 324 Director eval;
- 52 Narrative eval;
- 432 семантических семей;
- нет family leakage между train/eval;
- Narrative-ответы не повторяются дословно.

v3 усиливает `CHECK`, `DONE`, `NPC_UPSERT`, `QUEST_FAIL`, `WORLD_RESOLVE` и точность `name/value`. Рассказчику даны разнообразные ответы длиной примерно 140–320 символов.

## Важное изменение v3: режимы

В обучении используются явные маркеры:

```text
<MODE_DIRECTOR>
<MODE_NARRATOR>
```

Перед использованием v3-адаптера такие же строки нужно добавить в Android-промпты. Подробности: [`docs/ANDROID_MODE_MARKERS.md`](docs/ANDROID_MODE_MARKERS.md).

## Использование существующего окружения

```bash
cd ~/Downloads/mydnd-llm-training
source ../dnd_gemma_qlora_latest/.venv/bin/activate
./mydnd.sh doctor
```

Ничего переустанавливать не нужно, если `doctor` показывает CUDA и рабочий Unsloth.

## Основной цикл

```bash
./mydnd.sh prepare
./mydnd.sh audit
./mydnd.sh train
./mydnd.sh eval-director quick
./mydnd.sh eval-narrator quick
```

Или одной командой:

```bash
./mydnd.sh all
```

Полная проверка:

```bash
./mydnd.sh eval-director full
./mydnd.sh eval-narrator full
```

Результаты появляются в `reports/`, логи — в `logs/`, адаптер — в `outputs/`.

## Как добавлять новые datasets

Создать шаблон:

```bash
./mydnd.sh new-pack director_inventory_v4 director
```

или:

```bash
./mydnd.sh new-pack narrator_dialogues_v4 narrative
```

Затем отредактировать созданный JSONL и выполнить:

```bash
./mydnd.sh prepare
./mydnd.sh audit
```

Все `datasets/packs/*.jsonl` подключаются автоматически. Редактировать Python-код или общий огромный JSONL не требуется.

Подробнее: [`docs/ADDING_DATASETS.md`](docs/ADDING_DATASETS.md).

## Рекомендуемый эксперимент v3

Параметры находятся в `config/default.json`:

```text
model: Gemma 4 E2B bnb-4bit
context: 1280
learning rate: 4e-5
epochs: 1.7
LoRA rank: 8
effective batch: 8
```

Learning rate ниже, чем в v2, чтобы меньше сдвигать стиль рассказчика.

## GitHub

После распаковки или клонирования:

```bash
git init -b main
git add .
git commit -m "Initial MyDND LLM training v3"
git remote add origin git@github.com:USERNAME/mydnd-llm-training.git
git push -u origin main
```

Дальше обновление проекта:

```bash
git pull
```

Добавление нового набора:

```bash
git add datasets/packs/my_new_pack.jsonl
git commit -m "Add new inventory hard cases"
git push
```
