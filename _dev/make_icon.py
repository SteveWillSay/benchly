"""Generate assets/icon.ico — teal gradient rounded square with a pulse line."""

from PIL import Image, ImageDraw

SIZE = 256


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build(size=SIZE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Benchly brand: warm sunset gradient (gold -> orange -> terracotta),
    # angled bottom-left to top-right
    stops = [(233, 196, 106), (244, 162, 97), (231, 111, 81)]   # #e9c46a #f4a261 #e76f51
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        for x in range(0, size, 2):
            t = ((x / size) + (1 - y / size)) / 2   # 0 at bottom-left, 1 at top-right
            c = lerp(stops[0], stops[1], t * 2) if t < 0.5 else lerp(stops[1], stops[2], (t - 0.5) * 2)
            gd.point((x, y), fill=c + (255,))
            gd.point((x + 1, y), fill=c + (255,))

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    radius = size // 4.5
    md.rounded_rectangle([8, 8, size - 8, size - 8], radius=int(radius), fill=255)
    img.paste(grad, (0, 0), mask)

    # pulse line (ECG style)
    w = max(int(size * 0.075), 4)
    mid = size * 0.52
    pts = [
        (size * 0.14, mid),
        (size * 0.32, mid),
        (size * 0.42, size * 0.26),
        (size * 0.56, size * 0.74),
        (size * 0.66, mid),
        (size * 0.86, mid),
    ]
    ink = (58, 24, 8)
    shadow = [(x + size * 0.012, y + size * 0.018) for x, y in pts]
    draw.line(shadow, fill=ink + (70,), width=w, joint="curve")
    draw.line(pts, fill=ink + (255,), width=w, joint="curve")
    r = w // 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=ink + (255,))
    return img


img = build()
img.save(r"F:\Surprise App\assets\icon.png")
img.save(r"F:\Surprise App\assets\icon.ico",
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
