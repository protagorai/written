#!/usr/bin/env python3
"""
env_setup.py

Purpose:
- Load environment variables for ocr_batch_submit.py from a .env file (no extra deps).
- Validate required keys.
- Optionally generate a .env.template with stub values.

Usage:
  # 1) Create a template you can copy/edit into .env
  python env_setup.py --write-template

  # 2) Load .env (default in current directory) and export into this process
  python env_setup.py --file .env

Integration (at the very top of ocr_batch_submit.py):
  try:
      import env_setup
      env_setup.load_env_file()  # loads ".env" by default, validates required keys
  except Exception as e:
      print(f"[ENV] {e}")

Required keys:
  - OPENAI_API_KEY

Optional keys (supported by your script):
  - OPENAI_ORG
  - OPENAI_PROJECT
  - MODEL_ID  (lets you override the model id via env if desired)

This loader:
- Supports lines like KEY=VALUE, KEY="VALUE", KEY='VALUE', and "export KEY=VALUE".
- Ignores comments (# ...) and blank lines.
- Performs simple ${VAR} interpolation against already-parsed keys and os.environ.
- Does not overwrite existing environment variables unless --override is passed.
"""

from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable

REQUIRED_KEYS = ["OPENAI_API_KEY"]
OPTIONAL_KEYS = ["OPENAI_ORG", "OPENAI_PROJECT", "MODEL_ID"]

TEMPLATE_CONTENT = """# .env.template — copy to .env and fill real values
# REQUIRED
OPENAI_API_KEY=sk-REPLACE_ME

# OPTIONAL
# Organization and project (if applicable to your OpenAI account)
OPENAI_ORG=org-REPLACE_ME
OPENAI_PROJECT=proj-REPLACE_ME

# Model override (your ocr_batch_submit.py can read this if you wire it)
MODEL_ID=gpt-5-thinking
"""

_KEY_VAL_RE = re.compile(
    r"""^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>.*)\s*$"""
)

_VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")

def _unquote(val: str) -> str:
    val = val.strip()
    if (len(val) >= 2) and ((val[0] == val[-1]) and val[0] in ("'", '"')):
        q = val[0]
        inner = val[1:-1]
        if q == '"':
            # Interpret common escapes inside double quotes
            inner = (
                inner
                .replace(r"\n", "\n")
                .replace(r"\r", "\r")
                .replace(r"\t", "\t")
                .replace(r"\\", "\\")
                .replace(r"\"", "\"")
            )
        else:
            # Single quotes: treat as mostly literal (only unescape \' and \\)
            inner = inner.replace(r"\'", "'").replace(r"\\", "\\")
        return inner
    return val

def _interpolate(val: str, scope: Dict[str, str]) -> str:
    """
    Replace ${VAR} or $VAR with values from scope or os.environ if present.
    Simple one-pass (sufficient for most .env files).
    """
    def repl(m):
        name = m.group(1)
        if name in scope:
            return scope[name]
        return os.environ.get(name, m.group(0))
    return _VAR_REF_RE.sub(repl, val)

def parse_dotenv(text: str) -> Dict[str, str]:
    """
    Parse .env content into a dict without touching os.environ.
    Supports:
      - comments (#) and blank lines
      - 'export KEY=VALUE'
      - single/double quotes
      - ${VAR} interpolation
    """
    parsed: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = _KEY_VAL_RE.match(line)
        if not m:
            # Skip malformed lines silently
            continue
        key, val = m.group("key"), m.group("val")
        val = _unquote(val)
        val = _interpolate(val, {**os.environ, **parsed})
        parsed[key] = val
    return parsed

def load_env_file(
    path: str | Path = ".env",
    required_keys: Iterable[str] = REQUIRED_KEYS,
    optional_keys: Iterable[str] = OPTIONAL_KEYS,
    override: bool = False,
    strict: bool = True,
) -> Dict[str, str]:
    """
    Read .env file and populate os.environ (optionally not overriding existing vars).
    - required_keys: ensure these exist in the final environment; raise if missing and strict=True.
    - optional_keys: not enforced; included for template generation and docs.
    Returns dict of keys loaded/affected (not including pre-existing ones if override=False).
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        if strict:
            raise FileNotFoundError(f".env file not found at: {p.resolve()}")
        else:
            return {}

    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = p.read_text(encoding="utf-8", errors="ignore")
    env_map = parse_dotenv(text)

    applied: Dict[str, str] = {}
    for k, v in env_map.items():
        if (k in os.environ) and not override:
            continue
        os.environ[k] = v
        applied[k] = v

    # Validate required keys (can come from file or pre-existing env)
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing and strict:
        raise EnvironmentError(f"Missing required env var(s): {', '.join(missing)}")

    return applied

def write_template(path: str | Path = ".env.template", force: bool = False) -> Path:
    """
    Write a .env.template with stub values.
    Won't overwrite an existing file unless force=True.
    """
    p = Path(path)
    if p.exists() and not force:
        raise FileExistsError(f"{p} already exists. Use --force to overwrite.")
    p.write_text(TEMPLATE_CONTENT, encoding="utf-8")
    return p

def main():
    ap = argparse.ArgumentParser(description="Load .env and/or generate .env.template for OCR script.")
    ap.add_argument("--file", "-f", default=".env", help="Path to the .env file to load (default: .env)")
    ap.add_argument("--override", action="store_true", help="Override already-set environment variables")
    ap.add_argument("--strict", action="store_true", help="Raise error if .env missing or required keys absent")
    ap.add_argument("--write-template", "-t", action="store_true", help="Write .env.template with stub values")
    ap.add_argument("--template-path", default=".env.template", help="Where to write the template (default: .env.template)")
    ap.add_argument("--force", action="store_true", help="Overwrite existing .env.template")
    ap.add_argument("--print", dest="do_print", action="store_true", help="Print keys loaded/affected")
    args = ap.parse_args()

    if args.write_template:
        try:
            out = write_template(args.template_path, force=args.force)
            print(f"Wrote template: {out}")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        applied = load_env_file(
            path=args.file,
            required_keys=REQUIRED_KEYS,
            optional_keys=OPTIONAL_KEYS,
            override=args.override,
            strict=args.strict,
        )
        if args.do_print:
            if applied:
                print("Loaded/updated keys:")
                for k in sorted(applied):
                    print(f"  {k}={'*' * 8 if k.endswith('KEY') else os.environ.get(k, '')}")
            else:
                print("No keys loaded (either .env empty or all vars already set and --override not used).")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
