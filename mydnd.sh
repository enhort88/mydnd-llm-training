#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CONFIG="${MYDND_TRAIN_CONFIG:-config/default.json}"

usage() {
  cat <<'EOF'
MyDND LLM training project

Commands:
  ./mydnd.sh doctor                  Check CUDA and Python libraries
  ./mydnd.sh model-cache             Put the base model in a stable local folder once
  ./mydnd.sh prepare                 Compile all datasets/packs/*.jsonl
  ./mydnd.sh audit                   Validate compiled datasets
  ./mydnd.sh train                   Train the v3 LoRA adapter
  ./mydnd.sh eval-director [quick|full]
  ./mydnd.sh eval-narrator [quick|full]
  ./mydnd.sh all                     prepare + audit + train + quick evaluations
  ./mydnd.sh export [q8_0|q4_k_m]    Export the trained adapter to GGUF
  ./mydnd.sh regenerate-v3           Rebuild committed v3 generated packs
  ./mydnd.sh new-pack NAME [director|narrative]

The model, .venv, outputs and reports are not stored in Git.
EOF
}

json_value() {
  python - "$1" <<'PY'
import json, sys
from pathlib import Path
cfg=json.loads(Path('config/default.json').read_text(encoding='utf-8'))
print(cfg[sys.argv[1]])
PY
}

cmd="${1:-}"
case "$cmd" in
  doctor)
    python doctor.py
    ;;
  model-cache)
    python cache_model.py --config "$CONFIG"
    ;;
  prepare)
    python prepare_dataset.py
    ;;
  audit)
    python audit_dataset.py
    ;;
  train)
    mkdir -p logs
    python train_qlora.py --config "$CONFIG" 2>&1 | tee logs/train-v3.log
    ;;
  eval-director)
    mode="${2:-quick}"
    limit=0
    [[ "$mode" == "quick" ]] && limit="$(json_value director_quick_limit)"
    mkdir -p reports logs
    python compare_director.py --config "$CONFIG" --limit "$limit" \
      --report "reports/director-v3-${mode}.json" 2>&1 | tee "logs/director-v3-${mode}.log"
    ;;
  eval-narrator)
    mode="${2:-quick}"
    limit=0
    [[ "$mode" == "quick" ]] && limit="$(json_value narrative_quick_limit)"
    mkdir -p reports logs
    python compare_narrative.py --config "$CONFIG" --limit "$limit" \
      --report "reports/narrative-v3-${mode}.json" 2>&1 | tee "logs/narrative-v3-${mode}.log"
    ;;
  export)
    quant="${2:-q8_0}"
    python export_gguf.py --config "$CONFIG" --quantization "$quant"
    ;;
  all)
    "$0" prepare
    "$0" audit
    "$0" train
    "$0" eval-director quick
    "$0" eval-narrator quick
    ;;
  regenerate-v3)
    python tools/generate_v3_packs.py
    python prepare_dataset.py
    python audit_dataset.py
    ;;
  new-pack)
    name="${2:-}"
    kind="${3:-director}"
    [[ -n "$name" ]] || { echo "Pack name is required" >&2; exit 2; }
    python new_pack.py "$name" --kind "$kind"
    ;;
  *)
    usage
    [[ -z "$cmd" ]] || exit 2
    ;;
esac
