"""Optional helper to render cheatsheets as PNGs or PDFs if extra libs are installed.

Usage: python scripts/generate_cheatsheets.py
Installs: Pillow (for PNG), reportlab (for PDF) — not required for core app.
"""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'app' / 'demo_assets'


def load_md(file: Path):
    return file.read_text(encoding='utf-8')


def attempt_generate_png(md_text, out_path: Path):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        print('Pillow not installed; skipping PNG generation')
        return
    # Simple rendering: write text onto a white image (no advanced wrapping)
    lines = md_text.splitlines()
    width = 1200
    line_h = 22
    height = line_h * (len(lines) + 4)
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    y = 10
    for line in lines:
        draw.text((10, y), line, fill='black', font=font)
        y += line_h
    img.save(out_path)
    print(f'Wrote {out_path}')


def main():
    for md in BASE.glob('cheatsheet_*.md'):
        text = load_md(md)
        out_png = md.with_suffix('.png')
        attempt_generate_png(text, out_png)


if __name__ == '__main__':
    main()
