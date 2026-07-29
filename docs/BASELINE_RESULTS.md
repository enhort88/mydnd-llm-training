# Зафиксированный baseline перед v3

На v2, Gemma 4 E2B, 120 Director holdout:

| Метрика | Base | v2 LoRA |
|---|---:|---:|
| tool syntax | 92.5% | 93.3% |
| Java contract valid | 5.0% | 85.8% |
| action type accuracy | 10.0% | 65.8% |
| identity fields accuracy | 0.8% | 55.8% |
| all fields exact | 0.0% | 25.0% |

Narrative v2 сохранил нулевую утечку tools, но средняя длина упала примерно с 278 до 135 символов и появились повторяющиеся ответы. v3 создан именно для исправления этой деградации.
