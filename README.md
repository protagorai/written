🧭📄  EXPORT / ROTATE / OCR  🤖📊  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
🖼  Export PDFs to page images  
⟲  Auto-orient scanned pages (LTR text)  
🤖  Batch OCR with a multimodal model  
✅  Validate results and save JSON

## What’s in this repo?

- `orient.py` — Auto-rotate images to upright (0/90/180/270).  
  Two-stage logic: (A) layout signal to separate {0,180} vs {90,270};  
  (B) 0↔180 disambiguation using OCR confidence + margin asymmetry.

- `export.py` — Export each PDF page to an image (PNG/JPEG/TIFF…).

- `ocr_batch_submit.py` — Group page images, send to a multimodal model  
  (e.g., `gpt-5-thinking`), capture strict JSON, then ask a second  
  “Is this adequate?” validator (Yes/No).

- `env_setup.py` — Tiny `.env` loader and `.env.template` generator.  
  No external deps. Validates `OPENAI_API_KEY`.

- `.env.template` — Copy to `.env`, set your keys.

> All tools are CLI-first, single-file scripts: easy to skim, easy to hack.


## Quickstart (5 minutes)

1) Create & activate a virtual environment (recommended)

    python -m venv .venv
    . .venv/bin/activate    # Windows: .venv\Scripts\activate

2) Install Python dependencies

    pip install --upgrade pip
    pip install pillow opencv-python pytesseract pymupdf openai

3) Install the Tesseract **binary** (needed for best orientation & OCR confidence)  
   - macOS (Homebrew):  brew install tesseract  
   - Ubuntu/Debian:     sudo apt-get install tesseract-ocr  
   - Windows (Chocolatey):  choco install tesseract

   Optionally add language data for Serbian: `srp`, `srp_latn`.

4) Create your `.env` and set the API key

    python env_setup.py --write-template
    cp .env.template .env
    # edit .env and set OPENAI_API_KEY=sk-...

   You can later validate:

    python env_setup.py --file .env --strict --print

5) Export PDF pages to images

    python export.py docs/report.pdf -o images -f png -d 300

   Output will look like:
   - `images/report_0.png`, `images/report_1.png`, …

6) Auto-orient your images (in-place overwrite)

    python orient.py images --lang "srp+srp_latn+eng"

   Use `--dry-run` first if you want to preview changes without writing.

7) Prepare the OCR prompt & (optional) reference list
   - `prompt.txt` — your extraction instructions (what JSON you expect).
   - `liste.txt`  — optional list of known candidate/party names (one per line).

8) Run the batch OCR

    python ocr_batch_submit.py --images images --prompt prompt.txt --out json --list liste.txt

   This will save one `<group>.json` per logical report group under `./json/`.

That’s it! You now have upright page images and structured OCR JSON.

---

## Typical pipeline

1.  PDF → images (DPI you choose)  
2.  ⟲ Fix page orientation (0/90/180/270)  
3.  🤖 Send grouped images with your `prompt.txt` to the model  
4.  ✅ Second pass validator answers “Yes/No”  
5.  💾 Save JSON per group

Pictogram of the flow:

[PDF] 📄 → 🖼  (pages) → ⟲  → 🖼✅ → 🤖 → 📦 JSON


## Install notes

- Python 3.8+ is supported.
- Core pip packages: `pillow`, `opencv-python`, `pytesseract`, `pymupdf`, `openai`.
- For Tesseract:
  - Ensure the executable is on your `PATH` (e.g., `tesseract --version` works).
  - Install language packs for best results on Serbian (`srp`, `srp_latn`).


## Repo structure (suggested)

    .
    ├── orient.py
    ├── export.py
    ├── ocr_batch_submit.py
    ├── env_setup.py
    ├── .env.template
    ├── prompt.txt            # you create this
    ├── liste.txt             # optional
    ├── images/               # output of export.py
    └── json/                 # output of ocr_batch_submit.py


## Key commands (copy/paste)

- Export PDFs (300 DPI PNG):

    python export.py -d 300 -f png -o images my_reports.pdf

- Rotate images in place (Serbian languages active):

    python orient.py images --lang "srp+srp_latn+eng"

- Dry run (no writing) + recurse subfolders:

    python orient.py images --dry-run --recursive --lang "srp+srp_latn+eng"

- Submit OCR batches to `gpt-5-thinking`:

    python ocr_batch_submit.py --images images --prompt prompt.txt --out json --list liste.txt --model gpt-5-thinking


## Orientation logic (why it’s robust)

- Stage A — **Layout signal** (no OCR):  
  We compare horizontal vs vertical line structure. If horizontal lines dominate, it’s in the {0°,180°} family; if vertical dominates, it’s {90°,270°}.

- Stage B — **0° vs 180°**:  
  - Prefer **OCR confidence comparison** (Tesseract) between 0° and 180°.  
  - Fallback **margin asymmetry**: top margin is typically smaller than bottom on real documents.

- We still consult Tesseract OSD; it’s great at spotting 90°/270° on printed pages.


## Grouping logic for OCR

Files with the same base name and trailing page suffixes are grouped:

- `report.png`, `report_1.png`, `report-2.png`, `report (3).png` → one group “report”.

Each group is sent in one multimodal request with all pages + your prompt.


## Environment variables

Set via `.env` (loaded by `env_setup.py`):

- Required: `OPENAI_API_KEY`
- Optional:  `OPENAI_ORG`, `OPENAI_PROJECT`, `MODEL_ID` (default: `gpt-5-thinking`)

You can override the model with:

    export MODEL_ID=gpt-5-thinking


## Data & safety

- `orient.py` overwrites images in place. Use `--dry-run` first.  
- `export.py` writes new image files; use `--overwrite` to replace existing ones.  
- `ocr_batch_submit.py` writes JSON into your `--out` folder; it does not modify inputs.

---

## Need help?

- See `TROUBLESHOOTING.md` for environment and runtime issues.
- See `ORIENTATION.md` for orientation tuning tips.
- See `OCR.md` for prompt design and result validation tips.
- See `ENV.md` for environment loading and `.env` template details.

Have fun!  ⟲📄→🤖→📦

---

# FILE: TROUBLESHOOTING.md

# Troubleshooting

This guide lists common pitfalls and quick fixes.

## 1) “Command not found” or imports fail

- `tesseract: command not found`
  - Install the Tesseract binary and ensure it’s on your PATH.
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
  - Windows (Chocolatey): `choco install tesseract`
  - Restart your shell or terminal so PATH updates take effect.

- `ImportError: No module named ...`
  - You’re missing a Python package (or not in your venv).
  - Re-activate your venv, then:
  
        pip install pillow opencv-python pytesseract pymupdf openai

## 2) OpenAI authentication issues

- Error mentions missing or invalid API key:
  - Create `.env` from `.env.template` and set `OPENAI_API_KEY=sk-...`.
  - Validate with:
  
        python env_setup.py --file .env --strict --print

- Organization / project errors:
  - If your account uses them, set `OPENAI_ORG` and/or `OPENAI_PROJECT` in `.env`.

## 3) “No PNG files found.”

- `ocr_batch_submit.py` by default only reads `*.png` in the given folder (non-recursive).
- Ensure you exported pages to PNGs, or point it at a file instead of a directory.
- If your images are JPEGs, either convert them to PNGs or extend `PNG_EXTS` in the script.

## 4) Pages still upside-down

- Install Tesseract and Serbian language packs; pass `--lang "srp+srp_latn+eng"`.
- Increase effective resolution (export PDFs at 300–400 DPI, or scan higher).
- For faint handwriting, orientation improves after light denoise; our script applies this, but higher DPI still helps.
- If only a handful fail, re-run `orient.py` on those files with `--dry-run` to check the chosen degrees.

## 5) Poor OCR/JSON quality

- Your `prompt.txt` might be too loose. Be explicit: field names, types, examples, and strict JSON requirement.
- Provide a small reference list in `liste.txt` (one item per line) to help normalization, but **do not** make the model guess—your prompt should instruct it to use references only if visually present.
- Check the images are upright and 300–400 DPI. Lower DPI hurts handwriting.

## 6) Validator always says “No”

- The validator compares your `prompt.txt` requirements to the JSON result.  
  If your prompt demands fields the model can’t see (e.g., not on the page), it will fail.
- Loosen the prompt or provide multiple pages per group so all evidence is available.

## 7) Windows paths & quoting

- Wrap paths with spaces in quotes:
  
        python export.py "C:\Users\me\My Docs\file.pdf"

## 8) PyMuPDF warnings or encrypted PDFs

- Use `--password "secret"` for protected PDFs.
- If pages don’t export, try lowering DPI (e.g., `-d 200`) or check that the PDF opens in a viewer.

## 9) Rate limits / network hiccups

- The scripts include simple retry backoff. For larger batches, consider adding `--sleep 0.5` between groups.

## 10) JSON parse errors

- We try to recover by extracting the first `{...}` block. If that still fails, the raw text is saved under `"raw_response"` with `"parse_error"` set.

---

# FILE: ORIENTATION.md

# Image Orientation (orient.py)

⟲ Ensure that text lines read left→right and stack top→bottom.

## Usage

- Dry-run (preview only):

        python orient.py images --dry-run --lang "srp+srp_latn+eng"

- Overwrite in place:

        python orient.py images --lang "srp+srp_latn+eng"

- Single file:

        python orient.py images/page_12.png --lang "srp+srp_latn+eng"

- Recurse subfolders:

        python orient.py images --recursive --lang "srp+srp_latn+eng"

## How it decides

1) Stage A — 0/180 vs 90/270  
   We binarize and compare horizontal vs vertical projection variance. Horizontal dominance → {0,180}.

2) Stage B — 0 vs 180  
   - Prefer higher Tesseract OCR confidence between 0° and 180° images.  
   - Fallback: top/bottom whitespace ratio (documents usually have a bigger bottom margin).

3) Tesseract OSD is still consulted, especially effective for 90°/270° on printed text.

## Tips for handwriting & tables

- Use Serbian language packs in Tesseract: `srp`, `srp_latn`.
- Export/scan at 300–400 DPI (or upsample small images before OCR).
- Margins: if notebooks show punch-holes/shadows at the left edge, trimming 1–2% border can help the whitespace heuristic (you can add a crop step before analysis if needed).

## Safety

- The script overwrites files by design. Run `--dry-run` first.
- If evidence is weak, the script errs on the side of not rotating 0↔180 (keeps as-is).


---

# FILE: OCR.md

# OCR Batch Submit (ocr_batch_submit.py)

Batch-send image groups + instructions to a multimodal model (e.g., `gpt-5-thinking`).  
Saves JSON per group and a second pass “adequate?” verdict.

## Inputs

- `--images`  — folder with `*.png` (top-level only) or a single `*.png` file.
- `--prompt`  — text file with your extraction instructions and strict JSON schema.
- `--list`    — optional `liste.txt` containing known names (one per line).
- `--out`     — output folder for JSON files.
- `--model`   — model id (default from `MODEL_ID` or `gpt-5-thinking`).

## Grouping logic

Files are grouped by *base name without the trailing page suffix*:

- Examples mapping to group “report”:
  - `report.png`, `report_1.png`, `report-2.png`, `report (3).png`, `report page 4.png`

Each group is sent as one message with **all** its images.

## Example

    # Ensure env is loaded (or rely on env_setup auto-load)
    python env_setup.py --file .env --strict --print

    # Run OCR
    python ocr_batch_submit.py --images ./images --prompt ./prompt.txt --out ./json --list ./liste.txt --model gpt-5-thinking

The script will print each group, call the model, parse the first JSON block, run a Yes/No validator, and save `<group>.json`.

## Output JSON

- Your schema (as guided by `prompt.txt`).  
- Extra keys we add:
  - `is_adequate` — `"Yes"` or `"No"` from the validator pass.
  - `_validator_model` — model id used for the validator.
  - `_input_files` — list of image filenames in the group.
  - `_reference_list_used` — whether a list was provided.
  - `_reference_list_sample` — first few names from your list (for traceability).
  - `parse_error` / `raw_response` — only if parsing failed.

## Prompt tips

- Be explicit: list fields, types, and a minimal JSON example.
- State clearly: “Return **only** valid JSON, no extra text.”
- Describe normalization rules for names (Cyrillic/Latin) and numbers (commas vs dots).
- If a field is absent on the page, require it to be omitted or set to `null` (choose one).

## Rate-limit hygiene

- Add `--sleep 0.25` (or similar) for large batches.


---