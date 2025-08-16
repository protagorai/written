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