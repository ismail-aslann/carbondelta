"""Uygulama ikonunu üretir: desktop/icon.png (pencere) ve desktop/icon.ico (EXE).

Çalıştır: python data_build\\make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desktop"
SIZE = 512
BG_TOP = (22, 120, 92)
BG_BOTTOM = (12, 74, 64)
WHITE = (255, 255, 255)


def draw(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # Dikey degrade zemin
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        k = y / (size - 1)
        color = tuple(round(a + (b - a) * k) for a, b in zip(BG_TOP, BG_BOTTOM)) + (255,)
        gd.line([(0, y), (size, y)], fill=color)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    s = size / 512
    # Delta üçgeni: dış dolu üçgenden içteki küçültülmüş üçgen çıkarılır (temiz köşeler).
    outer = [(256 * s, 78 * s), (440 * s, 410 * s), (72 * s, 410 * s)]
    cx = sum(p[0] for p in outer) / 3
    cy = sum(p[1] for p in outer) / 3
    inner = [(cx + (x - cx) * 0.70, cy + (y - cy) * 0.70) for x, y in outer]
    ring = Image.new("L", (size, size), 0)
    rd = ImageDraw.Draw(ring)
    rd.polygon(outer, fill=255)
    rd.polygon(inner, fill=0)
    img.paste(Image.new("RGBA", (size, size), WHITE + (255,)), (0, 0), ring)
    # Aşağı ok: emisyon düşüşü
    d.line([(256 * s, 210 * s), (256 * s, 330 * s)], fill=WHITE, width=round(30 * s))
    d.polygon([(206 * s, 300 * s), (306 * s, 300 * s), (256 * s, 356 * s)], fill=WHITE)
    return img


def chevron(direction: str, size: int = 32, color=(91, 103, 118, 255)) -> Image.Image:
    """Giriş alanları için ok simgesi (stil sayfasında küçültülerek kullanılır)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = [(size * 0.2, size * 0.35), (size * 0.5, size * 0.65), (size * 0.8, size * 0.35)]
    if direction == "up":
        pts = [(x, size - y) for x, y in pts]
    d.line(pts, fill=color, width=round(size * 0.12), joint="curve")
    return img


def main() -> None:
    ui = OUT / "ui"
    ui.mkdir(exist_ok=True)
    chevron("down").save(ui / "chevron_down.png")
    chevron("up").save(ui / "chevron_up.png")
    chevron("down", color=(190, 198, 206, 255)).save(ui / "chevron_down_disabled.png")
    chevron("up", color=(190, 198, 206, 255)).save(ui / "chevron_up_disabled.png")
    img = draw()
    img.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                      (128, 128), (256, 256)])
    print("Yazıldı:", OUT / "icon.png", OUT / "icon.ico")


if __name__ == "__main__":
    main()
