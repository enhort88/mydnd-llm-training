#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def load_project_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(value: str | os.PathLike[str], root: Path = ROOT) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    return path if path.is_absolute() else root / path


def find_binary(llama_dir: Path, name: str) -> Path | None:
    candidates = [
        llama_dir / name,
        llama_dir / "bin" / name,
        llama_dir / "build" / "bin" / name,
        llama_dir / "build" / "bin" / "Release" / name,
    ]
    found = shutil.which(name)
    if found:
        candidates.insert(0, Path(found))
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
    return None


def ensure_llama_cpp(llama_dir: Path) -> Path:
    converter = llama_dir / "convert_lora_to_gguf.py"
    if converter.is_file():
        return llama_dir

    if llama_dir.exists() and any(llama_dir.iterdir()):
        raise SystemExit(
            f"{llama_dir} exists, but convert_lora_to_gguf.py is missing. "
            "Pass --llama-cpp-dir pointing to a full llama.cpp checkout."
        )

    llama_dir.parent.mkdir(parents=True, exist_ok=True)
    run([
        "git", "clone", "--depth", "1",
        "https://github.com/ggml-org/llama.cpp.git",
        str(llama_dir),
    ])
    if not converter.is_file():
        raise SystemExit(f"llama.cpp clone completed, but {converter} was not found")
    return llama_dir


def ensure_export_lora(llama_dir: Path) -> Path:
    binary = find_binary(llama_dir, "llama-export-lora")
    if binary:
        return binary

    build_dir = llama_dir / "build"
    run([
        "cmake", "-S", str(llama_dir), "-B", str(build_dir),
        "-DBUILD_SHARED_LIBS=OFF", "-DGGML_CUDA=OFF",
    ])
    run([
        "cmake", "--build", str(build_dir), "--config", "Release",
        "-j", str(max(1, os.cpu_count() or 1)),
        "--target", "llama-export-lora",
    ])
    binary = find_binary(llama_dir, "llama-export-lora")
    if not binary:
        raise SystemExit("llama-export-lora was built but the binary could not be located")
    return binary


def parse_args() -> argparse.Namespace:
    config_path = ROOT / "config" / "default.json"
    cfg = load_project_config(config_path)
    default_adapter = cfg.get("output_dir", "outputs/mydnd-e2b-v3-lora")
    default_base_hf = cfg.get("local_model_dir", "~/Models/MyDND/gemma-4-E2B-training")

    parser = argparse.ArgumentParser(
        description=(
            "Convert the MyDND PEFT adapter to GGUF LoRA and merge it into an "
            "existing GGUF of the exact same Gemma 4 E2B base model."
        )
    )
    parser.add_argument("--base-gguf", required=True, help="Exact E2B base GGUF used for the merge")
    parser.add_argument("--adapter", default=default_adapter, help="LoRA adapter directory")
    parser.add_argument("--base-hf", default=default_base_hf, help="Local HF base directory used for training")
    parser.add_argument("--output", help="Output merged GGUF path")
    parser.add_argument("--llama-cpp-dir", default="tools/llama.cpp", help="Full llama.cpp checkout")
    parser.add_argument("--keep-lora-gguf", action="store_true", help="Keep intermediate GGUF LoRA")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_gguf = resolve_path(args.base_gguf)
    adapter = resolve_path(args.adapter)
    base_hf = resolve_path(args.base_hf)
    llama_dir = resolve_path(args.llama_cpp_dir)

    for path, description in (
        (base_gguf, "base GGUF"),
        (adapter / "adapter_config.json", "adapter_config.json"),
        (base_hf / "config.json", "base HF config.json"),
    ):
        if not path.exists():
            raise SystemExit(f"Missing {description}: {path}")

    if args.output:
        output = resolve_path(args.output)
    else:
        output = ROOT / "outputs" / f"{base_gguf.stem}-mydnd-v3.gguf"
    output.parent.mkdir(parents=True, exist_ok=True)

    work_dir = ROOT / "outputs" / ".mydnd-gguf-export"
    work_dir.mkdir(parents=True, exist_ok=True)
    lora_gguf = work_dir / "mydnd-e2b-v3-lora-f16.gguf"

    llama_dir = ensure_llama_cpp(llama_dir)
    converter = llama_dir / "convert_lora_to_gguf.py"
    export_lora = ensure_export_lora(llama_dir)

    if output.exists():
        output.unlink()
    if lora_gguf.exists():
        lora_gguf.unlink()

    print("\n[1/2] Converting PEFT adapter to GGUF LoRA...", flush=True)
    run([
        sys.executable,
        str(converter),
        "--base", str(base_hf),
        "--outfile", str(lora_gguf),
        "--outtype", "f16",
        str(adapter),
    ])

    if not lora_gguf.is_file() or lora_gguf.stat().st_size == 0:
        raise SystemExit(f"LoRA GGUF was not created: {lora_gguf}")

    print("\n[2/2] Merging GGUF LoRA into the base GGUF...", flush=True)
    run([
        str(export_lora),
        "-m", str(base_gguf),
        "-o", str(output),
        "--lora", str(lora_gguf),
    ])

    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit(f"Merged GGUF was not created: {output}")

    if not args.keep_lora_gguf:
        lora_gguf.unlink(missing_ok=True)

    size_gib = output.stat().st_size / 1024**3
    print("\nGGUF merge finished")
    print(f"Output: {output.resolve()}")
    print(f"Size:   {size_gib:.2f} GiB")
    print("Important: the output keeps the base GGUF tensor quantization.")
    print("Use the exact E2B base checkpoint; an E4B or unrelated GGUF is incompatible.")


if __name__ == "__main__":
    main()
