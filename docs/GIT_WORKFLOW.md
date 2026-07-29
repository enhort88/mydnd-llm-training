# Git workflow

## Первый запуск

```bash
git clone <URL> mydnd-llm-training
cd mydnd-llm-training
source /path/to/existing/.venv/bin/activate
./mydnd.sh prepare
./mydnd.sh audit
```

Модель остаётся вне репозитория и берётся из локального Hugging Face cache либо `~/Models/MyDND/gemma-4-E2B-training`.

## Новая партия примеров

```bash
./mydnd.sh new-pack director_checks_v4 director
# редактируем datasets/packs/director_checks_v4.jsonl
./mydnd.sh prepare
./mydnd.sh audit
git add datasets/packs/director_checks_v4.jsonl
git commit -m "Add Director check hard cases"
git push
```

## Новый эксперимент

Не менять старый config задним числом. Скопировать его:

```bash
cp config/default.json config/e2b-v4.json
```

Запустить:

```bash
MYDND_TRAIN_CONFIG=config/e2b-v4.json ./mydnd.sh train
```

Так результаты можно воспроизвести по commit + config.
