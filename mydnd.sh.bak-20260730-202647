#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CONFIG="${MYDND_TRAIN_CONFIG:-config/default.json}"
LLAMA_CPP_DIR="${MYDND_LLAMA_CPP:-$ROOT/tools/llama.cpp}"
DEFAULT_F16_OUT="${MYDND_F16_OUT:-outputs/mydnd-gemma-4-E2B-v3-F16.gguf}"
DEFAULT_Q4_OUT="${MYDND_Q4_OUT:-outputs/mydnd-gemma-4-E2B-v3-Q4_0.gguf}"
DEFAULT_QUANT_TYPE="${MYDND_QUANT_TYPE:-Q4_0}"

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
  ./mydnd.sh export BASE_GGUF [OUTPUT_F16]
                                    Merge trained LoRA into base GGUF → always *-F16.gguf
  ./mydnd.sh quantize INPUT_F16 OUTPUT_Q4 [TYPE]
                                    Quantize F16 GGUF with llama-quantize (default TYPE=Q4_0)
  ./mydnd.sh verify MODEL.gguf [EXPECTED_FTYPE]
                                    Check real ftype via llama-cli; reject Q4 name + F16 body
  ./mydnd.sh all BASE_GGUF           train → export F16 → quantize Q4_0 → verify
  ./mydnd.sh regenerate-v3           Rebuild committed v3 generated packs
  ./mydnd.sh new-pack NAME [director|narrative]

Environment:
  MYDND_EXPORT_BASE_HF   HF base for LoRA conversion (default: ~/Models/MyDND/gemma-4-E2B-it-BF16)
  MYDND_LLAMA_CPP        llama.cpp checkout (default: tools/llama.cpp)
  MYDND_F16_OUT / MYDND_Q4_OUT / MYDND_QUANT_TYPE  defaults for all/export/quantize

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

die() {
  echo "error: $*" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# llama.cpp binary discovery / build
# ---------------------------------------------------------------------------

find_llama_bin() {
  local name="$1"
  local candidates=(
    "$LLAMA_CPP_DIR/build/bin/$name"
    "$LLAMA_CPP_DIR/build/bin/Release/$name"
    "$LLAMA_CPP_DIR/bin/$name"
    "$LLAMA_CPP_DIR/$name"
    "$HOME/.unsloth/llama.cpp/$name"
  )
  local found
  found="$(command -v "$name" 2>/dev/null || true)"
  [[ -n "$found" ]] && candidates=("$found" "${candidates[@]}")

  local path
  for path in "${candidates[@]}"; do
    if [[ -f "$path" && -x "$path" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

ensure_llama_bin() {
  local name="$1"
  local path
  if path="$(find_llama_bin "$name")"; then
    printf '%s\n' "$path"
    return 0
  fi

  [[ -d "$LLAMA_CPP_DIR" ]] || die "llama.cpp not found at $LLAMA_CPP_DIR (set MYDND_LLAMA_CPP)"
  [[ -f "$LLAMA_CPP_DIR/CMakeLists.txt" ]] || die "not a llama.cpp tree: $LLAMA_CPP_DIR"

  local build_dir="$LLAMA_CPP_DIR/build"
  echo "Building $name in $build_dir ..." >&2
  cmake -S "$LLAMA_CPP_DIR" -B "$build_dir" \
    -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=OFF
  cmake --build "$build_dir" --config Release \
    -j "$(nproc 2>/dev/null || echo 1)" \
    --target "$name"

  path="$(find_llama_bin "$name")" || die "built $name but binary not found"
  printf '%s\n' "$path"
}

# ---------------------------------------------------------------------------
# GGUF ftype verification via llama-cli
# ---------------------------------------------------------------------------

# Print real ftype string from llama-cli (e.g. F16, Q4_0). Empty on failure.
get_gguf_ftype() {
  local model="$1"
  local cli
  cli="$(ensure_llama_bin llama-cli)"

  # Interactive llama-cli hangs on the prompt; close stdin and bound runtime.
  # Banner line looks like:  ftype      : Q4_0
  local output
  output="$(
    timeout 300 "$cli" \
      -m "$model" \
      -p "verify" \
      -n 1 \
      --no-warmup \
      -c 64 \
      </dev/null 2>&1 || true
  )"

  printf '%s\n' "$output" | sed -n 's/^ftype[[:space:]]*:[[:space:]]*//p' | head -1
}

normalize_ftype() {
  # Uppercase, strip whitespace and MOSTLY_ prefix if present.
  local t
  t="$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"
  t="${t#MOSTLY_}"
  printf '%s\n' "$t"
}

is_float_ftype() {
  case "$(normalize_ftype "$1")" in
    F16|BF16|F32|F64) return 0 ;;
    *) return 1 ;;
  esac
}

# Fail if filename implies Q4* but the model body is still F16/BF16/F32.
assert_name_matches_ftype() {
  local path="$1"
  local ftype="$2"
  local base
  base="$(basename "$path")"

  if [[ "$base" =~ [Qq]4 ]] && is_float_ftype "$ftype"; then
    die "filename contains Q4 but internal ftype is $(normalize_ftype "$ftype"): $path
Refusing to ship a mislabeled F16 model as Q4. Run: ./mydnd.sh quantize <F16> <OUTPUT_Q4>"
  fi
}

# verify_gguf PATH [EXPECTED]
# Prints size / ftype / sha256. Exits non-zero on mismatch or name/body conflict.
verify_gguf() {
  local path="$1"
  local expected="${2:-}"

  [[ -f "$path" ]] || die "GGUF not found: $path"

  echo "Verifying ftype via llama-cli: $path"
  local ftype
  ftype="$(get_gguf_ftype "$path")"
  [[ -n "$ftype" ]] || die "could not read ftype from llama-cli for: $path"

  local norm
  norm="$(normalize_ftype "$ftype")"
  assert_name_matches_ftype "$path" "$norm"

  if [[ -n "$expected" ]]; then
    local exp
    exp="$(normalize_ftype "$expected")"
    # Accept Q4_0 matching Q4_0; F16 matching F16; also allow "Q4" prefix match for family.
    if [[ "$norm" != "$exp" ]]; then
      # Soft family match: expected Q4_0, got Q4_0 / Q4_1 / Q4_K_M etc only if exact.
      die "ftype mismatch for $path: got $norm, expected $exp"
    fi
  fi

  local bytes size_h sha
  bytes="$(stat -c '%s' "$path")"
  size_h="$(numfmt --to=iec-i --suffix=B "$bytes" 2>/dev/null || echo "${bytes} bytes")"
  sha="$(sha256sum "$path" | awk '{print $1}')"

  echo "OK: $path"
  echo "  ftype   : $norm"
  echo "  size    : $size_h ($bytes bytes)"
  echo "  sha256  : $sha"

  # Export for callers that want machine-readable values.
  VERIFY_FTYPE="$norm"
  VERIFY_BYTES="$bytes"
  VERIFY_SHA256="$sha"
}

# Enforce export output naming: must end with F16.gguf, must not look like Q4.
resolve_f16_output() {
  local output="${1:-}"
  if [[ -z "$output" ]]; then
    output="$DEFAULT_F16_OUT"
  fi

  local base
  base="$(basename "$output")"

  if [[ "$base" =~ [Qq]4 ]]; then
    die "export output must not contain Q4 in the name (got: $base).
export always produces F16. Use: ./mydnd.sh quantize <F16> <OUTPUT_Q4> [TYPE]"
  fi

  # Accept *.F16.gguf / *-F16.gguf / *F16.gguf (case-insensitive).
  if [[ ! "$base" =~ [Ff]16\.gguf$ ]]; then
    die "export output must end with F16.gguf (got: $base).
Example: outputs/mydnd-gemma-4-E2B-v3-F16.gguf"
  fi

  printf '%s\n' "$output"
}

cmd_export() {
  local base_gguf="${1:-}"
  local output_raw="${2:-}"
  local base_hf="${MYDND_EXPORT_BASE_HF:-$HOME/Models/MyDND/gemma-4-E2B-it-BF16}"

  [[ -n "$base_gguf" ]] || die "Usage: ./mydnd.sh export BASE_GGUF [OUTPUT_F16]"

  # Name policy first: never accept Q4 labels for the F16 export stage.
  local output
  output="$(resolve_f16_output "$output_raw")"

  [[ -f "$base_gguf" ]] || die "Base GGUF not found: $base_gguf"
  [[ -f "$base_hf/config.json" ]] || die "BF16 HF base not found: $base_hf (expected config.json)"

  mkdir -p "$(dirname "$output")"

  echo "=== export: merge LoRA → F16 GGUF ==="
  echo "base GGUF : $base_gguf"
  echo "HF base   : $base_hf"
  echo "output    : $output"

  python tools/export_gguf_from_base.py \
    --base-hf "$base_hf" \
    --base-gguf "$base_gguf" \
    --output "$output" \
    --llama-cpp-dir "$LLAMA_CPP_DIR"

  verify_gguf "$output" "F16"
}

cmd_quantize() {
  local input="${1:-}"
  local output="${2:-}"
  local qtype="${3:-$DEFAULT_QUANT_TYPE}"

  [[ -n "$input" && -n "$output" ]] || die "Usage: ./mydnd.sh quantize INPUT_F16 OUTPUT_Q4 [TYPE]"
  [[ -f "$input" ]] || die "Input GGUF not found: $input"

  local qtype_norm
  qtype_norm="$(normalize_ftype "$qtype")"

  local out_base
  out_base="$(basename "$output")"
  if [[ ! "$out_base" =~ [Qq]4 ]]; then
    echo "warning: output name does not contain Q4 ($out_base); continuing with type $qtype_norm" >&2
  fi

  mkdir -p "$(dirname "$output")"

  echo "=== quantize: $input → $output ($qtype_norm) ==="

  # Input must be a float model before quantizing.
  echo "Checking input ftype..."
  local in_ftype
  in_ftype="$(get_gguf_ftype "$input")"
  [[ -n "$in_ftype" ]] || die "could not read ftype of input: $input"
  assert_name_matches_ftype "$input" "$in_ftype"
  if ! is_float_ftype "$in_ftype"; then
    die "quantize expects F16/BF16/F32 input, got $(normalize_ftype "$in_ftype"): $input"
  fi
  echo "Input ftype OK: $(normalize_ftype "$in_ftype")"

  local quant
  quant="$(ensure_llama_bin llama-quantize)"

  # llama-quantize model-f16.gguf model-quant.gguf type
  echo "+ $quant $input $output $qtype_norm"
  "$quant" "$input" "$output" "$qtype_norm"

  [[ -f "$output" && -s "$output" ]] || die "quantize produced no file: $output"

  verify_gguf "$output" "$qtype_norm"
}

cmd_verify() {
  local path="${1:-}"
  local expected="${2:-}"
  [[ -n "$path" ]] || die "Usage: ./mydnd.sh verify MODEL.gguf [EXPECTED_FTYPE]"
  verify_gguf "$path" "$expected"
}

cmd_all() {
  local base_gguf="${1:-${MYDND_BASE_GGUF:-}}"
  [[ -n "$base_gguf" ]] || die "Usage: ./mydnd.sh all BASE_GGUF
Or set MYDND_BASE_GGUF to the F16 (or compatible) base GGUF used for LoRA merge."

  local f16_out="$DEFAULT_F16_OUT"
  local q4_out="$DEFAULT_Q4_OUT"
  local qtype="$DEFAULT_QUANT_TYPE"

  echo "========================================"
  echo "MyDND all: train → export F16 → quantize → verify"
  echo "  base GGUF : $base_gguf"
  echo "  F16 out   : $f16_out"
  echo "  Q4 out    : $q4_out  ($qtype)"
  echo "========================================"

  echo
  echo ">>> [1/4] train"
  mkdir -p logs
  python train_qlora.py --config "$CONFIG" 2>&1 | tee logs/train-v3.log

  echo
  echo ">>> [2/4] merge/export F16"
  cmd_export "$base_gguf" "$f16_out"

  echo
  echo ">>> [3/4] quantize $qtype"
  cmd_quantize "$f16_out" "$q4_out" "$qtype"

  echo
  echo ">>> [4/4] final verify"
  verify_gguf "$q4_out" "$(normalize_ftype "$qtype")"

  echo
  echo "========================================"
  echo "Pipeline complete"
  echo "  final   : $q4_out"
  echo "  ftype   : ${VERIFY_FTYPE}"
  echo "  size    : $(numfmt --to=iec-i --suffix=B "${VERIFY_BYTES}" 2>/dev/null || echo "${VERIFY_BYTES} bytes")"
  echo "  sha256  : ${VERIFY_SHA256}"
  echo "========================================"
}

# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

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
    shift
    cmd_export "${1:-}" "${2:-}"
    ;;
  quantize)
    shift
    cmd_quantize "${1:-}" "${2:-}" "${3:-}"
    ;;
  verify)
    shift
    cmd_verify "${1:-}" "${2:-}"
    ;;
  all)
    shift
    cmd_all "${1:-}"
    ;;
  regenerate-v3)
    python tools/generate_v3_packs.py
    python prepare_dataset.py
    python audit_dataset.py
    ;;
  new-pack)
    name="${2:-}"
    kind="${3:-director}"
    [[ -n "$name" ]] || die "Pack name is required"
    python new_pack.py "$name" --kind "$kind"
    ;;
  *)
    usage
    [[ -z "$cmd" ]] || exit 2
    ;;
esac
