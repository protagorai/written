🧭📄  EXPORT / ROTATE / OCR  🤖📊  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
🖼  Export PDFs to page images  
⟲  Auto-orient scanned pages (LTR text)  
🤖  Batch OCR with a multimodal model  
✅  Validate results and save JSON

## What’s in this repo?

- `export.py` — Export each PDF page to an image (PNG/JPEG/TIFF…).

- `orient.py` — Auto-rotate images to upright (0/90/180/270).  
  Two-stage logic: (A) layout signal to separate {0,180} vs {90,270};  
  (B) 0↔180 disambiguation using OCR confidence + margin asymmetry.

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
