#!/usr/bin/env python3
"""
Auto-rotate document images to upright (0/90/180/270).

Improvements vs previous version:
- Two-stage orientation:
  Stage A: 0/180 vs 90/270 via projection variance (no OCR).
  Stage B: disambiguate 0 vs 180 by:
      (1) OCR confidence comparison with Tesseract (if available),
      (2) fallback to layout asymmetry (top vs bottom whitespace).
- Keeps EXIF for JPEGs where possible and overwrites files in-place.

Install:
  pip install pillow opencv-python pytesseract
  + Tesseract binary and language packs (e.g., srp, srp_latn, eng)
"""

import argparse
import os
import sys
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageOps
import cv2

try:
    import pytesseract
    HAVE_TESS = True
except Exception:
    HAVE_TESS = False

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

# ---------- Image helpers ----------

def is_image_path(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS

def rotate_pil_90s(img: Image.Image, deg_cw: int) -> Image.Image:
    """Rotate by multiples of 90 CW using lossless transposes."""
    d = deg_cw % 360
    if d == 0:
        return img
    if d == 90:
        return img.transpose(Image.ROTATE_270)  # PIL's constant is CCW
    if d == 180:
        return img.transpose(Image.ROTATE_180)
    if d == 270:
        return img.transpose(Image.ROTATE_90)
    return img.rotate(-deg_cw, expand=True)

def pil_to_gray(img: Image.Image) -> np.ndarray:
    if img.mode == "L":
        return np.array(img, dtype=np.uint8)
    arr = np.array(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

def binarize(gray: np.ndarray) -> np.ndarray:
    """Adaptive/robust binarization -> text=1, background=0."""
    # light denoise
    g = cv2.GaussianBlur(gray, (3,3), 0)
    # combine Otsu and adaptive to be friendlier to handwriting
    _, th_otsu = cv2.threshold(255 - g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th_adp = cv2.adaptiveThreshold(255 - g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 35, 15)
    th = cv2.bitwise_or(th_otsu, th_adp)
    return (th > 0).astype(np.uint8)

# ---------- Stage A: 0/180 vs 90/270 ----------

def proj_variance_score(bin_img: np.ndarray) -> float:
    hproj = bin_img.sum(axis=1).astype(np.float32)
    vproj = bin_img.sum(axis=0).astype(np.float32)
    if hproj.size: hproj /= (bin_img.shape[1] + 1e-9)
    if vproj.size: vproj /= (bin_img.shape[0] + 1e-9)
    return float(hproj.var() / (vproj.var() + 1e-9))

def pick_pair_0_180_or_90_270(img: Image.Image) -> Tuple[int, int]:
    """
    Return the better pair: (0,180) or (90,270).
    We compute projection-variance scores for 0 and 90 and pick the higher.
    """
    # scale moderate for robustness/speed
    w,h = img.size
    scale = min(1.0, 1600 / max(w,h))
    work = img if scale==1.0 else img.resize((int(w*scale), int(h*scale)), Image.BILINEAR)

    scores = {}
    for d in (0, 90):
        r = rotate_pil_90s(work, d)
        gray = pil_to_gray(r)
        bin_img = binarize(gray)
        scores[d] = proj_variance_score(bin_img)

    if scores[0] >= scores[90]:
        return (0, 180)
    else:
        return (90, 270)

# ---------- Stage B: 0 vs 180 disambiguation ----------

def ocr_confidence_score(img: Image.Image, lang: Optional[str]) -> Tuple[float, int]:
    """
    Return (mean_conf, alpha_num_count). If Tesseract unavailable or failure, (-1, 0).
    """
    if not HAVE_TESS:
        return (-1.0, 0)
    try:
        # modest up/downscale helps OCR on faint handwriting
        w,h = img.size
        long_side = max(w,h)
        if long_side < 900:
            s = 900/long_side
            img = img.resize((int(w*s), int(h*s)), Image.BILINEAR)

        cfg_lang = lang if lang else None
        data = pytesseract.image_to_data(img, lang=cfg_lang, output_type=pytesseract.Output.DICT)
        confs = []
        alnum = 0
        for txt, conf in zip(data.get("text", []), data.get("conf", [])):
            try:
                c = float(conf)
            except Exception:
                continue
            if c <= 0:
                continue
            if txt and any(ch.isalnum() for ch in txt):
                confs.append(c)
                alnum += sum(ch.isalnum() for ch in txt)
        mean_conf = float(np.mean(confs)) if confs else -1.0
        return (mean_conf, alnum)
    except Exception:
        return (-1.0, 0)

def whitespace_top_bottom_ratio(img: Image.Image) -> float:
    """
    Heuristic: top margin is usually smaller than bottom.
    Return top_whitespace / (bottom_whitespace + 1).
    Lower is better for 'upright'.
    """
    gray = pil_to_gray(img)
    bin_img = binarize(gray)
    rows = bin_img.sum(axis=1)
    H = rows.shape[0]
    # find first and last 'ink' row
    thresh = max(10, int(0.01 * bin_img.shape[1]))  # ink if row has enough white pixels
    top_idx = next((i for i,v in enumerate(rows) if v > thresh), 0)
    bot_idx = next((i for i,v in enumerate(rows[::-1]) if v > thresh), 0)
    bottom_last = H - 1 - bot_idx
    top_ws = top_idx
    bottom_ws = max(0, H - 1 - bottom_last)
    return top_ws / (bottom_ws + 1e-6)

def choose_0_vs_180(img: Image.Image, lang: Optional[str]) -> int:
    """
    Return 0 or 180 for 'upright'. Prefer OCR confidence; fallback to whitespace heuristic.
    """
    # 1) OCR comparison
    conf0, al0 = ocr_confidence_score(img, lang)
    conf180, al180 = ocr_confidence_score(rotate_pil_90s(img, 180), lang)

    if conf0 >= 0 or conf180 >= 0:
        # combine mean conf + a tiny bonus for more recognized chars
        s0 = conf0 + 0.05 * np.log1p(al0) if conf0 >= 0 else -1e9
        s180 = conf180 + 0.05 * np.log1p(al180) if conf180 >= 0 else -1e9
        if s0 != s180:
            return 0 if s0 > s180 else 180

    # 2) Layout asymmetry fallback
    r0 = whitespace_top_bottom_ratio(img)
    r180 = whitespace_top_bottom_ratio(rotate_pil_90s(img, 180))
    # Prefer the orientation with smaller top/bottom ratio
    if abs(r0 - r180) > 0.05:
        return 0 if r0 < r180 else 180

    # 3) If still ambiguous, keep as-is
    return 0

# ---------- OSD (still useful for 90/270 and printed pages) ----------

def tesseract_osd_deg(img: Image.Image) -> Optional[int]:
    if not HAVE_TESS:
        return None
    try:
        w,h = img.size
        long_side = max(w,h)
        if long_side > 2000:
            s = 2000/long_side
            im = img.resize((int(w*s), int(h*s)), Image.BILINEAR)
        else:
            im = img
        osd = pytesseract.image_to_osd(im)
        for line in osd.splitlines():
            if "Rotate:" in line:
                deg = int(line.split(":")[1].strip()) % 360
                if deg in (0,90,180,270):
                    return deg
        return None
    except Exception:
        return None

# ---------- Decision logic ----------

def decide_orientation(img: Image.Image, lang: Optional[str]) -> int:
    """
    Final rotation in CW degrees to make image upright.
    """
    # Normalize any EXIF rotation effects already outside
    # Try OSD first for a quick win on printed pages
    deg_osd = tesseract_osd_deg(img)
    if deg_osd in (90, 270):
        return deg_osd
    # For 0/180 from OSD we still verify with Stage B (helps handwriting/tables)
    # Stage A: choose pair
    a, b = pick_pair_0_180_or_90_270(img)
    if (a, b) == (0, 180):
        d = choose_0_vs_180(img, lang)
        return d
    else:  # (90,270) -> we know it's sideways; pick which one
        # Decide between 90 and 270 by OCR confidence if available; else projection variance
        img90 = rotate_pil_90s(img, 90)
        img270 = rotate_pil_90s(img, 270)
        conf90, al90 = ocr_confidence_score(img90, lang)
        conf270, al270 = ocr_confidence_score(img270, lang)
        if conf90 >= 0 or conf270 >= 0:
            s90 = conf90 + 0.05*np.log1p(al90) if conf90>=0 else -1e9
            s270 = conf270 + 0.05*np.log1p(al270) if conf270>=0 else -1e9
            return 90 if s90 >= s270 else 270
        # fallback: pick higher proj variance
        s90v = proj_variance_score(binarize(pil_to_gray(img90)))
        s270v = proj_variance_score(binarize(pil_to_gray(img270)))
        return 90 if s90v >= s270v else 270

# ---------- I/O ----------

def save_with_exif_preserved(src: Image.Image, out_img: Image.Image, path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    exif = src.info.get("exif")
    params = {}
    if ext in (".jpg", ".jpeg"):
        params.update(dict(quality=95, subsampling="keep", optimize=True))
        if exif: params["exif"] = exif
    out_img.save(path, **params)

def process_image(path: str, lang: Optional[str], dry_run: bool=False) -> Tuple[bool, Optional[int]]:
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)  # neutralize EXIF Orientation
            deg = decide_orientation(im, lang)
            if deg % 360 == 0:
                return (False, 0)
            rot = rotate_pil_90s(im, deg)
            if not dry_run:
                save_with_exif_preserved(im, rot, path)
            return (True, deg)
    except Exception as e:
        print(f"[ERROR] {path}: {e}", file=sys.stderr)
        return (False, None)

def iter_paths(root: str, recursive: bool):
    if os.path.isfile(root):
        if is_image_path(root):
            yield root
        return
    if recursive:
        for dp, _, fns in os.walk(root):
            for fn in fns:
                p = os.path.join(dp, fn)
                if is_image_path(p): yield p
    else:
        for fn in os.listdir(root):
            p = os.path.join(root, fn)
            if os.path.isfile(p) and is_image_path(p): yield p

def main():
    ap = argparse.ArgumentParser(description="Auto-rotate document images upright (LTR text).")
    ap.add_argument("input_path", help="File or folder")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--dry-run", action="store_true", help="Report without writing")
    ap.add_argument("--lang", default=None,
                    help="Tesseract language(s), e.g. 'srp+srp_latn+eng'. Ignored if Tesseract not installed.")
    args = ap.parse_args()

    paths = list(iter_paths(args.input_path, args.recursive))
    if not paths:
        print("No supported images found.")
        return

    changed = 0
    total = 0
    for p in paths:
        total += 1
        chg, deg = process_image(p, args.lang, args.dry_run)
        if deg is None:
            print(f"[SKIP] {p}")
        elif chg:
            print(f"[ROTATED {deg:>3}°] {p}")
            changed += 1
        else:
            print(f"[ALREADY UPRIGHT] {p}")

    if args.dry_run:
        print(f"\nDry-run: {changed}/{total} would be rotated.")
    else:
        print(f"\nDone: rotated {changed}/{total} images.")

if __name__ == "__main__":
    main()
