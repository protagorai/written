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