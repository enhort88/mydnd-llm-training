#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
CONFIG="config/e2b-v4.json"

case "${1:-}" in
  prepare)
    python prepare_dataset_v4.py
    python tools/generate_v4_stress_holdout.py
    ;;
  audit)
    python audit_dataset_v4.py
    ;;
  smoke)
    rm -rf outputs/mydnd-e2b-v4-smoke
    python train_qlora.py --config "$CONFIG" --max-steps 30 --output-dir outputs/mydnd-e2b-v4-smoke
    python compare_director.py --config "$CONFIG" --adapter outputs/mydnd-e2b-v4-smoke \
      --eval-file datasets/holdout/v4_director_stress.jsonl --limit 80 --skip-base \
      --report reports/director-v4-smoke.json
    ;;
  train)
    mkdir -p logs
    python train_qlora.py --config "$CONFIG" 2>&1 | tee logs/train-v4-compact.log
    ;;
  eval-quick)
    mkdir -p reports logs
    python compare_director.py --config "$CONFIG" --limit 320 --skip-base \
      --report reports/director-v4-quick.json 2>&1 | tee logs/director-v4-quick.log
    python compare_narrative.py --config "$CONFIG" --limit 80 --skip-base \
      --report reports/narrative-v4-quick.json 2>&1 | tee logs/narrative-v4-quick.log
    ;;
  eval-stress)
    mkdir -p reports logs
    python compare_director.py --config "$CONFIG" --eval-file datasets/holdout/v4_director_stress.jsonl \
      --skip-base --report reports/director-v4-stress.json 2>&1 | tee logs/director-v4-stress.log
    python compare_narrative.py --config "$CONFIG" --eval-file datasets/holdout/v4_narrative_stress.jsonl \
      --skip-base --report reports/narrative-v4-stress.json 2>&1 | tee logs/narrative-v4-stress.log
    ;;
  overnight)
    "$0" prepare
    "$0" audit
    "$0" train
    "$0" eval-quick
    "$0" eval-stress
    ;;
  *)
    cat <<'EOF'
Usage:
  ./mydnd-v4.sh prepare      Build compact v4 train/eval and 2500-case stress holdout
  ./mydnd-v4.sh audit        Validate uniqueness, coverage and prompt-size reduction
  ./mydnd-v4.sh smoke        30-step sanity training + 80 Director cases
  ./mydnd-v4.sh train        Full v4 training
  ./mydnd-v4.sh eval-quick   Quick tuned-model evaluation
  ./mydnd-v4.sh eval-stress  Full independent 2000+500 stress holdout
  ./mydnd-v4.sh overnight    Prepare + audit + full train + all evaluations
EOF
    ;;
esac
