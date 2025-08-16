#!/usr/bin/env python3
"""
pdf2images.py — export PDF pages as images with zero-based suffixes.

Requires: pip install pymupdf

Examples:
  # Single PDF next to the source file, PNG at 200 DPI
  python pdf2images.py /path/to/file.pdf
  
  # or a bit more elaborate case
  python export.py pdfs -d 300 -o images -f png -s _

  # Multiple PDFs, recursive, JPEG at 300 DPI into ./out
  python pdf2images.py -r -o out -f jpg -d 300 docs/

  # Encrypted PDF (if needed)
  python pdf2images.py --password "secret" secured.pdf
"""
import argparse
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.stderr.write("Missing dependency: pip install pymupdf\n")
    sys.exit(1)


def export_pdf(
    pdf_path: Path,
    out_dir: Path | None = None,
    fmt: str = "png",
    dpi: int = 200,
    suffix_sep: str = "_",
    overwrite: bool = False,
    password: str | None = None,
) -> int:
    if out_dir is None:
        out_dir = pdf_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Cannot open {pdf_path}: {e}\n")
        return 0

    try:
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                sys.stderr.write(f"[ERROR] Password required or incorrect for {pdf_path}\n")
                doc.close()
                return 0

        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)  # scale to target DPI
        base = pdf_path.stem  # keep original base name
        pages_exported = 0

        for i in range(doc.page_count):
            try:
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat, alpha=False)  # opaque output
                out_name = f"{base}{suffix_sep}{i}.{fmt.lower()}"
                out_path = out_dir / out_name
                if out_path.exists() and not overwrite:
                    print(f"[SKIP] {out_path} exists (use --overwrite to replace)")
                    continue
                pix.save(out_path)
                pages_exported += 1
                print(f"[OK] {pdf_path.name} -> {out_path}")
            except Exception as pe:
                sys.stderr.write(f"[WARN] Page {i} failed for {pdf_path}: {pe}\n")

        return pages_exported
    finally:
        doc.close()


def iter_pdfs(target: Path, recursive: bool) -> list[Path]:
    if target.is_file() and target.suffix.lower() == ".pdf":
        return [target]
    if target.is_dir():
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return sorted(p for p in target.glob(pattern) if p.is_file())
    return []


def main():
    ap = argparse.ArgumentParser(description="Export PDF pages as images with zero-based suffixes.")
    ap.add_argument("paths", nargs="+", help="PDF files or directories containing PDFs")
    ap.add_argument("-o", "--out", type=Path, default=None, help="Output directory (default: alongside each PDF)")
    ap.add_argument("-f", "--format", choices=["png", "jpg", "jpeg", "tiff", "bmp"], default="png",
                    help="Image format/extension (default: png)")
    ap.add_argument("-d", "--dpi", type=int, default=200, help="Output DPI (default: 200)")
    ap.add_argument("-s", "--suffix-sep", default="_", help="Separator before page index (default: _)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing images")
    ap.add_argument("-r", "--recursive", action="store_true", help="Recurse into directories")
    ap.add_argument("--password", default=None, help="Password for encrypted PDFs (optional)")
    args = ap.parse_args()

    fmt = "jpg" if args.format.lower() == "jpeg" else args.format.lower()

    total_pages = 0
    seen_any = False

    for p in args.paths:
        target = Path(p)
        pdfs = iter_pdfs(target, args.recursive)
        if not pdfs and target.is_file():
            sys.stderr.write(f"[WARN] Not a PDF or not found: {target}\n")
        for pdf in pdfs:
            seen_any = True
            out_dir = args.out if args.out else pdf.parent
            total_pages += export_pdf(
                pdf_path=pdf,
                out_dir=out_dir,
                fmt=fmt,
                dpi=args.dpi,
                suffix_sep=args.suffix_sep,
                overwrite=args.overwrite,
                password=args.password,
            )

    if not seen_any:
        sys.stderr.write("[INFO] No PDFs found.\n")
    else:
        print(f"[DONE] Total pages exported: {total_pages}")


if __name__ == "__main__":
    main()
