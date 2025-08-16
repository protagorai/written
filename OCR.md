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