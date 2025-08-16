#!/usr/bin/env python3
"""
ocr_batch_submit.py

Quickstart:
python ocr_batch_submit.py --images ./images --prompt ./prompt.txt --out ./json

Full run with setup:
python env_setup.py --file .env --strict --print
python ocr_batch_submit.py --images ./images --prompt ./prompt.txt --out ./json


Batch-sends image groups (PNG pages of the same report) + a saved OCR prompt (prompt.txt)
to an OpenAI multimodal GPT-5 Thinking model, saves the model's JSON output per group,
then performs a second validation call asking: "Is this response adequate for this request?"
and stores "Yes"/"No" in the saved JSON.

WHAT YOU NEED TO EDIT / PROVIDE:
1) Install deps:  pip install --upgrade openai
2) Put your OCR instructions in: ./prompt.txt
3) (Optional) Put a *reference list* of expected candidates/parties in: ./liste.txt (one name per line).
   - The script will include this list if available and non-empty; otherwise it will ignore it.
4) Provide credentials (any of the following):
   - export OPENAI_API_KEY="sk-..."                 # required
   - optionally: OPENAI_ORG, OPENAI_PROJECT
5) Set MODEL_ID via .env or CLI:
   - .env: MODEL_ID=gpt-5-thinking
   - CLI:  --model gpt-5-thinking
6) Run:
   python ocr_batch_submit.py --images ./images --prompt ./prompt.txt --out ./json --list ./liste.txt

NOTES
- Only *.png files are considered (top-level of the given folder). Add extensions if you want more.
- Files that share the same base name except trailing numeric/similar suffixes are grouped
  (e.g., "report.png", "report_1.png", "report-2.png", "report (3).png" → one group).
- For each group, we send ONE request with the prompt + ALL images in that group.
- The model is expected to return STRICT JSON per your prompt. We still sanitize if needed.
- The second call is a simple validator that returns "Yes" or "No" only.
- The resulting JSON file is named: <group_prefix>.json (created under --out).
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# --- Load .env early so env vars are available before we read MODEL_ID ---
try:
    import env_setup
    env_setup.load_env_file(strict=False)  # loads .env if present; won’t overwrite existing env vars
except Exception as _e:
    print(f"[ENV] {_e}", file=sys.stderr)

# ---------- MODEL CONFIG (env-driven with fallback) ----------
MODEL_ID = os.getenv("MODEL_ID", "gpt-5-thinking")
# -------------------------------------------------------------

# ---- OpenAI client setup (reads env vars) ----
try:
    from openai import OpenAI
except ImportError:
    sys.stderr.write("Missing dependency: pip install --upgrade openai\n")
    sys.exit(1)

def make_client():
    """
    Initialize OpenAI client using environment variables:
      OPENAI_API_KEY (required)
      OPENAI_ORG (optional)
      OPENAI_PROJECT (optional)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        sys.stderr.write("ERROR: Please set OPENAI_API_KEY.\n")
        sys.exit(1)

    org = os.getenv("OPENAI_ORG")
    project = os.getenv("OPENAI_PROJECT")

    if org and project:
        return OpenAI(api_key=api_key, organization=org, project=project)
    elif org:
        return OpenAI(api_key=api_key, organization=org)
    else:
        return OpenAI(api_key=api_key)


# -------------- Utility functions --------------

PNG_EXTS = {".png"}  # adjust if you later want jpg/jpeg/tiff, etc.

_SUFFIX_PATTERNS = [
    r"[\s_\-]*(?:\(?\d+\)?)[\s]*$",             # _1, -2, (3), " 4"
    r"[\s_\-]*page[\s]*\d+[\s]*$",
    r"[\s_\-]*str(?:ana)?[\s]*\d+[\s]*$",       # str2, strana 3 (Serbian variants)
    r"[\s_\-]*pg[\s]*\d+[\s]*$",
]

def derive_group_key(stem: str) -> str:
    """
    Derive a grouping key by removing a single trailing page-like numeric suffix.
    We DO NOT strip internal digits (to avoid over-grouping different docs).
    """
    s = stem
    for pat in _SUFFIX_PATTERNS:
        s2 = re.sub(pat, "", s, flags=re.IGNORECASE)
        if s2 != s:
            s = s2
            break  # remove only one suffix occurrence
    return s.strip()

def group_images(paths: List[Path]) -> Dict[str, List[Path]]:
    """
    Group PNG images by normalized base name (without trailing numeric/similar suffix).
    Returns: dict[group_key] = [Path, Path, ...] (sorted by natural numeric order)
    """
    buckets: Dict[str, List[Path]] = {}
    for p in paths:
        stem = p.stem
        key = derive_group_key(stem).lower()
        buckets.setdefault(key, []).append(p)

    # Sort files in each group by a natural numeric key (page order)
    def natural_key(p: Path):
        # pick the trailing number if present for better page ordering
        m = re.search(r"(\d+)\D*$", p.stem)
        if m:
            try:
                return (int(m.group(1)), p.name)
            except Exception:
                pass
        return (10**9, p.name)

    for k in list(buckets.keys()):
        buckets[k].sort(key=natural_key)
    return buckets

def encode_image_to_data_url(path: Path) -> str:
    """
    Read PNG and return a data URL suitable for multimodal messages.
    """
    with path.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"

def ensure_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)

def extract_first_json_block(text: str) -> Tuple[dict, str]:
    """
    Try to parse JSON directly; if fails, extract the first {...} block and parse.
    Returns (parsed_json, raw_text). If parsing fails, returns ({}, raw_text).
    """
    raw = text.strip()
    # Fast path
    try:
        return json.loads(raw), raw
    except Exception:
        pass

    # Try to extract the first JSON object
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if m:
        candidate = m.group(0)
        try:
            return json.loads(candidate), raw
        except Exception:
            return {}, raw
    return {}, raw

def clamp_yes_no(s: str) -> str:
    s = (s or "").strip().lower()
    if s.startswith("y"):
        return "Yes"
    if s.startswith("n"):
        return "No"
    if "yes" in s:
        return "Yes"
    if "no" in s:
        return "No"
    return "No"  # be conservative


# -------- Optional candidate list (liste.txt) --------

def load_candidate_list(path: Optional[Path]) -> List[str]:
    """
    Load an optional reference list of candidate/party names (one per line).
    - Ignores empty lines and lines starting with '#' (comments).
    - Accepts UTF-8/UTF-8 BOM; falls back to cp1250 if needed; otherwise ignores undecodable bytes.
    - Deduplicates while preserving order.
    Returns [] if path is None, does not exist, or file is empty/malformed.
    """
    if not path:
        return []
    try:
        if not path.exists() or not path.is_file():
            return []
        # try a few encodings commonly used for Serbian text
        raw = path.read_bytes()
        text = None
        for enc in ("utf-8", "utf-8-sig", "cp1250"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="ignore")

        lines = []
        seen = set()
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s not in seen:
                seen.add(s)
                lines.append(s)
        return lines
    except Exception as e:
        sys.stderr.write(f"[WARN] Could not read liste: {path} ({e}). Ignoring.\n")
        return []


def format_reference_block(candidates: List[str]) -> str:
    """
    Build a compact, explicit reference section to pass to the model.
    """
    if not candidates:
        return ""
    header = (
        "REFERENCE CANDIDATES / LISTS (optional hints):\n"
        "- Use these names as lookup hints ONLY if they visibly appear (typed or handwritten) in the document.\n"
        "- Do NOT hallucinate absent names. If a listed name is not present, omit it from candidates.\n"
        "- Prefer exact visual matches (Cyrillic first, then Latin). If matched, normalize both scripts.\n"
    )
    body = "\n".join(f"- {name}" for name in candidates)
    return f"{header}{body}"


# -------------- OpenAI calls (multimodal) --------------

def call_model_json(
    client: OpenAI,
    model: str,
    prompt_text: str,
    image_paths: List[Path],
    candidate_list: Optional[List[str]] = None,
    max_retries: int = 3
) -> Tuple[dict, str]:
    """
    Send prompt + multiple images (+ optional reference candidate list) to the multimodal chat model.
    Returns (parsed_json, raw_text).
    """
    content = [{"type": "text", "text": prompt_text}]
    ref_block = format_reference_block(candidate_list or [])
    if ref_block:
        content.append({"type": "text", "text": ref_block})

    for p in image_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": encode_image_to_data_url(p)}
        })

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                # temperature=0.0,
                messages=[
                    {"role": "system", "content": prompt_text},  # keep the main instructions as system
                    {"role": "user", "content": content}
                ]
            )
            txt = resp.choices[0].message.content or ""
            parsed, raw = extract_first_json_block(txt)
            return parsed, raw
        except Exception as e:
            wait = 2 * attempt
            sys.stderr.write(f"[Retry {attempt}] model call failed: {e}\n")
            time.sleep(wait)

    return {}, ""


def call_validator_yes_no(
    client: OpenAI,
    model: str,
    prompt_text: str,
    response_json: dict,
    image_paths: List[Path],
    candidate_list: Optional[List[str]] = None,
    max_retries: int = 3
) -> str:
    """
    Ask the model to judge if the response_json adequately satisfies the prompt,
    returning strictly "Yes" or "No".
    """
    validator_system = (
        "You are a strict validator. Read the OCR prompt and the candidate JSON response. "
        "Check if the JSON fully satisfies the prompt's requirements. "
        "Answer with a single word only: Yes or No."
    )

    ref_block = format_reference_block(candidate_list or [])
    validator_user_text = (
        "PROMPT (requirements):\n"
        f"{prompt_text}\n\n"
        + (f"{ref_block}\n\n" if ref_block else "")
        + "CANDIDATE JSON RESPONSE:\n"
        f"{json.dumps(response_json, ensure_ascii=False)}\n\n"
        "Question: Is this response adequate for this request? Answer Yes or No only."
    )

    content = [{"type": "text", "text": validator_user_text}]
    for p in image_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": encode_image_to_data_url(p)}
        })

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                # temperature=0.0,
                # max_tokens=5,
                messages=[
                    {"role": "system", "content": validator_system},
                    {"role": "user", "content": content}
                ]
            )
            txt = (resp.choices[0].message.content or "").strip()
            return clamp_yes_no(txt)
        except Exception as e:
            wait = 2 * attempt
            sys.stderr.write(f"[Retry {attempt}] validator call failed: {e}\n")
            time.sleep(wait)

    return "No"


# ------------------- Main logic -------------------

def load_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"ERROR reading prompt file {path}: {e}\n")
        sys.exit(1)

def collect_pngs(root: Path) -> List[Path]:
    if root.is_dir():
        return sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in PNG_EXTS])
    elif root.is_file() and root.suffix.lower() in PNG_EXTS:
        return [root]
    else:
        return []

def safe_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", s)

def main():
    ap = argparse.ArgumentParser(description="Batch OCR sender for GPT-5 Thinking with validation (+ optional candidate list).")
    ap.add_argument("--images", required=True, help="Path to a folder with PNG files or a single PNG file.")
    ap.add_argument("--prompt", default="prompt.txt", help="Path to the OCR instruction prompt (default: prompt.txt).")
    ap.add_argument("--list", default="liste.txt", help="Optional path to a candidate list file (one name per line).")
    ap.add_argument("--out", default="json", help="Output folder for JSON results (default: json).")
    ap.add_argument(
        "--model",
        default=os.getenv("MODEL_ID", MODEL_ID),
        help=f"OpenAI model id (default: {os.getenv('MODEL_ID', MODEL_ID)})"
    )
    ap.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between groups (optional).")
    args = ap.parse_args()

    images_path = Path(args.images)
    prompt_path = Path(args.prompt)
    list_path = Path(args.list) if args.list else None
    out_dir = Path(args.out)
    ensure_dir(out_dir)

    prompt_text = load_prompt(prompt_path)
    reference_candidates = load_candidate_list(list_path)

    all_pngs = collect_pngs(images_path)
    if not all_pngs:
        sys.stderr.write("No PNG files found.\n")
        sys.exit(1)

    groups = group_images(all_pngs)
    client = make_client()

    print(f"[INFO] Using model: {args.model}")
    print(f"Found {sum(len(v) for v in groups.values())} images across {len(groups)} group(s).")
    if reference_candidates:
        print(f"Loaded {len(reference_candidates)} reference candidate name(s) from {list_path}.")
    else:
        print("No reference candidate list provided or the list is empty; proceeding without it.")

    for key, files in groups.items():
        group_prefix = safe_filename(key) if key else safe_filename(files[0].stem)
        out_file = out_dir / f"{group_prefix}.json"

        print(f"\n[GROUP] {group_prefix}  ({len(files)} image(s))")
        for f in files:
            print(f"  - {f.name}")

        # 1) Call main OCR/extraction
        response_json, raw_text = call_model_json(
            client, args.model, prompt_text, files, candidate_list=reference_candidates
        )

        # 2) If parsing failed, capture raw text
        result_obj: dict
        if response_json:
            result_obj = response_json
        else:
            result_obj = {
                "document_type": "unknown",
                "overall_confidence": 0.0,
                "parse_error": "Model did not return valid JSON. Raw response stored under 'raw_response'.",
                "raw_response": raw_text or ""
            }

        # Ensure document_type exists if model omitted it
        if "document_type" not in result_obj:
            if isinstance(result_obj.get("candidates"), list) and len(result_obj["candidates"]) > 0:
                result_obj["document_type"] = "report"
            else:
                result_obj["document_type"] = "other"

        # Record whether a reference list was provided
        result_obj["_reference_list_used"] = bool(reference_candidates)
        if reference_candidates:
            # Keep a small sample to avoid bloating output; full list is large and already known locally
            result_obj["_reference_list_sample"] = reference_candidates[:10]

        # 3) Validation call (Yes/No)
        validator_answer = call_validator_yes_no(
            client, args.model, prompt_text, result_obj, files, candidate_list=reference_candidates
        )

        # 4) Add validation result to JSON
        result_obj["is_adequate"] = validator_answer
        result_obj["_validator_model"] = args.model
        result_obj["_input_files"] = [str(p.name) for p in files]

        # 5) Save JSON
        try:
            out_file.write_text(json.dumps(result_obj, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[SAVED] {out_file}")
        except Exception as e:
            sys.stderr.write(f"ERROR writing {out_file}: {e}\n")

        if args.sleep > 0:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
