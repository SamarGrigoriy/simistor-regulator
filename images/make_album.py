#!/usr/bin/env python3
"""
Альбом изображений платы v2 и корпуса: PNG с номерами в images/ и один PDF.

    cd hw_1ch_v2
    python3 images/make_album.py

Исходники: images/src/ (слои и 3D платы из kicad-cli) и enclosure/build/
(картинки корпуса из enclosure/render.py). Скрипт ничего не рисует сам —
только раскладывает по страницам и подписывает.
"""
import os
import tempfile

import cairo
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
SRC = os.path.join(HERE, "src")
CASE = os.path.join(HW, "enclosure", "build")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PAGE = (1754, 1240)          # A4 альбомный, 150 dpi
MARGIN = 60

# (файл в альбоме, источник, заголовок, подпись)
ITEMS = [
    ("01_плата_сверху.png", f"{SRC}/board_top.png", "Плата: верх — медь F.Cu и шелкография",
     "80 × 70 мм, 2 слоя. Слева — сеть 230 В, справа — низковольтная часть, между ними полоса развязки. "
     "Клеммники на нижней кромке: L N (сеть), L' N (нагрузка), +5 DQ GND (датчик)."),
    ("02_плата_снизу.png", f"{SRC}/board_bottom.png", "Плата: низ — медь B.Cu и шелкография (вид снизу)",
     "В низковольтной части — сплошная земля. Подписи у площадок проводов ЖКИ и кнопок — для пайки снизу."),
    ("03_медь_F.png", f"{SRC}/board_FCu.png", "Медь F.Cu", "Силовые дорожки 4 А — 2 мм, сигналы — 0,25 мм, заливка землёй в низковольтной части."),
    ("04_медь_B.png", f"{SRC}/board_BCu.png", "Медь B.Cu",
     "Фаза L и ноль N — 2 мм; в низковольтной части — земля с одной короткой перемычкой (SWIO)."),
    ("05_сборочный.png", f"{SRC}/board_assembly.png", "Сборочный чертёж: шелкография и контуры деталей",
     "Позиционные обозначения, номиналы (серым) и контуры корпусов деталей."),
    ("06_3d_сверху.png", f"{SRC}/3d_top.png", "3D платы: вид сверху", ""),
    ("07_3d_изометрия.png", f"{SRC}/3d_iso.png", "3D платы: изометрия",
     "IRM-10-5 — модель из проекта energosint; у предохранителя F101 3D-модели нет — виден контур."),
    ("08_3d_снизу.png", f"{SRC}/3d_bottom.png", "3D платы: вид снизу", ""),
    ("09_корпус.png", f"{CASE}/view_closed.png", "Корпус в сборе",
     "87,9 × 75,8 × 46,1 мм, вариант 3 А. ЖКИ — точная модель модуля с переходником I2C. Провода — в окна нижней стенки, винты клеммников — отвёрткой через прорези в крышке."),
    ("10_корпус_лицо.png", f"{CASE}/view_front.png", "Лицевая панель",
     "ЖКИ 1602, кнопки МЕНЮ / − / +, прорези к винтам клеммников с подписями полюсов."),
    ("11_корпус_сверху_слева.png", f"{CASE}/view_closed_above.png", "Корпус: вид сверху слева", ""),
    ("12_корпус_низ.png", f"{CASE}/view_bottom_wall.png", "Нижняя стенка: окна под провода клеммников", ""),
    ("13_корпус_левая_стенка.png", f"{CASE}/view_left_wall.png", "Левая стенка: вентиляция у радиатора", ""),
    ("14_крышка_изнутри.png", f"{CASE}/view_lid_inside.png", "Крышка изнутри",
     "Стойки ЖКИ и держателя кнопок, трубки к винтам клеммников, бобышки боковых саморезов."),
    ("15_сборка_открыто.png", f"{CASE}/view_open.png", "Всё в сборе: крышка поднята", ""),
    ("16_сборка_внутри_сверху.png", f"{CASE}/view_inside_top.png", "Плата в основании, вид сверху",
     "Радиатор симистора — в левом нижнем углу, IRM-10-5 — чёрный блок."),
    ("17_сборка_внутри.png", f"{CASE}/view_inside_iso.png", "Плата в основании, изометрия", ""),
    ("18_взрыв_схема.png", f"{CASE}/view_exploded.png", "Взрыв-схема",
     "Снизу вверх: основание; плата с радиатором; держатель с кнопками и ЖКИ с переходником I2C; "
     "толкатели; крышка. Собирается в обратном порядке."),
    ("19_разрез_ЖКИ.png", f"{CASE}/view_section_lcd.png", "Разрез по ЖКИ",
     "Кнопки над IRM и держатель кнопок над симистором задают высоту корпуса."),
    ("20_разрез_симистор.png", f"{CASE}/view_section_triac.png", "Разрез по симистору", "Радиатор на изолированном фланце BTA416Y-800C, рёбра к левой стенке."),
]


def clean(im):
    """На белый фон; полупрозрачный фон окружения из рендера KiCad — тоже в белый."""
    if im.mode != "RGBA":
        return im.convert("RGB")
    r, g, b, a = im.split()
    a = a.point(lambda v: 0 if v < 230 else v)
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bg.paste(Image.merge("RGB", (r, g, b)), mask=a)
    return bg


def trim(im, pad=20):
    """Обрезать белые поля."""
    g = im.convert("L").point(lambda v: 255 if v < 250 else 0)
    box = g.getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def page(img, title, caption, num):
    land = img.width >= img.height
    W, H = PAGE if land else (PAGE[1], PAGE[0])
    pg = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(pg)
    ft, fc, fs = ImageFont.truetype(FONT_B, 34), ImageFont.truetype(FONT, 24), ImageFont.truetype(FONT, 20)
    d.text((MARGIN, MARGIN - 10), title, font=ft, fill=(20, 20, 20))
    cap = wrap(d, caption, fc, W - 2 * MARGIN) if caption else []
    top = MARGIN + 50
    bottom = H - MARGIN - 34 * len(cap) - 30
    box_w, box_h = W - 2 * MARGIN, bottom - top
    k = min(box_w / img.width, box_h / img.height)
    im = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    pg.paste(im, (MARGIN + (box_w - im.width) // 2, top + (box_h - im.height) // 2))
    y = bottom + 10
    for ln in cap:
        d.text((MARGIN, y), ln, font=fc, fill=(60, 60, 60))
        y += 34
    d.text((W - MARGIN - 160, H - MARGIN + 10), f"лист {num}", font=fs, fill=(140, 140, 140))
    d.text((MARGIN, H - MARGIN + 10), "Одноканальный регулятор, плата v2", font=fs, fill=(140, 140, 140))
    return pg


def cover(entries):
    W, H = PAGE
    pg = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(pg)
    d.text((MARGIN, 90), "Одноканальный симисторный регулятор", font=ImageFont.truetype(FONT_B, 52), fill=(20, 20, 20))
    d.text((MARGIN, 165), "Плата v2 и корпус 3 А — альбом изображений", font=ImageFont.truetype(FONT, 34), fill=(60, 60, 60))
    fc = ImageFont.truetype(FONT, 24)
    y, col = 270, 0
    for i, (_, _, title, _) in enumerate(entries, start=2):
        x = MARGIN + col * (W // 2)
        d.text((x, y), f"{i:2d}. {title}", font=fc, fill=(40, 40, 40))
        y += 40
        if y > H - 150 and col == 0:
            y, col = 270, 1
    d.text((MARGIN, H - 100), "CH32V006F8P6 · BTA416Y-800C · IRM-10-5 · ЖКИ 1602 I2C · DS18B20",
           font=ImageFont.truetype(FONT, 22), fill=(120, 120, 120))
    return pg


def main():
    pages, done = [], []
    for name, src, title, caption in ITEMS:
        if not os.path.exists(src):
            print("нет файла:", src)
            continue
        img = trim(clean(Image.open(src)))
        img.save(os.path.join(HERE, name))
        done.append((name, src, title, caption))
    pages.append(cover(done))
    for i, (name, src, title, caption) in enumerate(done, start=2):
        pages.append(page(Image.open(os.path.join(HERE, name)), title, caption, i))
    pdf = os.path.join(HERE, "регулятор_v2_альбом.pdf")
    write_pdf(pages, pdf)
    print(f"{len(done)} картинок, {len(pages)} листов: {pdf}")


def write_pdf(pages, path, dpi=150):
    """Листы-картинки в PDF через cairo (в этом Pillow нет JPEG-кодека для PDF)."""
    k = 72.0 / dpi
    surf = None
    with tempfile.TemporaryDirectory() as tmp:
        for i, pg in enumerate(pages):
            png = os.path.join(tmp, f"{i}.png")
            pg.save(png)
            w, h = pg.width * k, pg.height * k
            if surf is None:
                surf = cairo.PDFSurface(path, w, h)
            else:
                surf.set_size(w, h)
            ctx = cairo.Context(surf)
            ctx.scale(k, k)
            ctx.set_source_surface(cairo.ImageSurface.create_from_png(png), 0, 0)
            ctx.paint()
            surf.show_page()
        surf.finish()


if __name__ == "__main__":
    main()
