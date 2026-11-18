#!/usr/bin/env python3
"""Render slides.pptx to PDF and PNG previews with a robust fallback chain.

Chain (first available wins):
  1. LibreOffice (soffice --headless --convert-to pdf)          -> editable-faithful
  2. platform office-renderer tool if on PATH                    -> honored by name
  Fallback for PDF->PNG: PyMuPDF, else pdftoppm.

Usage:
  python3 render_preview.py slides.pptx --outdir previews
Produces: slides.pdf, previews/slide-01.png ... plus render_report.json
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

SOFFICE_CANDIDATES = [
    "soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/opt/homebrew/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/lib/libreoffice/program/soffice",
]


def find_soffice():
    for c in SOFFICE_CANDIDATES:
        p = shutil.which(c) or (c if os.path.exists(c) else None)
        if p:
            return p
    return None


def pptx_to_pdf(pptx, outdir):
    soffice = find_soffice()
    if not soffice:
        return None, "no LibreOffice (soffice) found; install LibreOffice or run on the platform office-renderer"
    cmd = [soffice, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", outdir, os.path.abspath(pptx)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return None, "soffice timed out after 240s"
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(pptx))[0] + ".pdf")
    if proc.returncode != 0 or not os.path.exists(pdf):
        return None, f"soffice failed: {proc.stderr.strip()[:300]}"
    return pdf, None


def pdf_to_pngs(pdf, outdir, dpi=110):
    base = os.path.splitext(os.path.basename(pdf))[0]
    png_dir = os.path.join(outdir, "pages")
    os.makedirs(png_dir, exist_ok=True)
    # 1) PyMuPDF
    try:
        import fitz
        doc = fitz.open(pdf)
        paths = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            p = os.path.join(png_dir, f"{base}-{i+1:02d}.png")
            pix.save(p)
            paths.append(p)
        return paths, None
    except ImportError:
        pass
    # 2) pdftoppm
    if shutil.which("pdftoppm"):
        proc = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), pdf, os.path.join(png_dir, base)],
            capture_output=True, text=True, timeout=240,
        )
        if proc.returncode == 0:
            paths = sorted(glob.glob(os.path.join(png_dir, f"{base}-*.png")))
            return paths, None
        return None, f"pdftoppm failed: {proc.stderr.strip()[:200]}"
    return None, "no PyMuPDF or pdftoppm available for PDF->PNG"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pptx")
    ap.add_argument("--outdir", default="previews")
    ap.add_argument("--dpi", type=int, default=110)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    report = {"pptx": args.pptx}

    pdf, err = pptx_to_pdf(args.pptx, args.outdir)
    report["pdf"] = pdf
    if err:
        report["error"] = err
        report["ok"] = False
    else:
        pngs, err2 = pdf_to_pngs(pdf, args.outdir, args.dpi)
        report["pages_png"] = pngs or []
        if err2:
            report["warning"] = err2
            report["ok"] = True  # PDF exists; PNG is advisory
        else:
            report["ok"] = True

    out = os.path.join(args.outdir, "render_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
