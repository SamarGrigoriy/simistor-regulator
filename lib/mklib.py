#!/usr/bin/env python3
"""
Библиотеки проекта.

Посадочные места (regulator1.pretty): клеммники Golten GT301-5.0 на 2 контакта
(сеть, нагрузка) и на 3 контакта (датчик). Генератор — пример из скилла
kicad-pcb (examples/footprints.py): размеры по чертежу GT301-5.0-XXP-XX-02AH,
отверстие 1,2 мм. Штатный MX126-5.0 KiCad совпадает шагом, но корпус сдвинут
на 0,9 мм — двор на плате уехал бы.

Оптроны в SMD — площадки по «рекомендованному рисунку площадок» даташитов
(файлы в корне проекта): EL817 опции S/S1 (DOC049414992.pdf, Everlight
DPC-0000046 Rev.14, стр. 9) и MOC305xS (DOC011314972.pdf, Lite-On
DS70-2001-025 Rev.E, разд. 7). У обоих одинаково: площадка 1,3 мм вдоль
вывода x 1,5 мм поперёк, шаг 2,54, центры рядов через 9,0 мм — между рядами
7,7 мм, по краям 10,3. Ножки ложатся: EL817 S1 — вылет до 10,3, стопа от 0,6;
MOC305xS — вылет 10,16+-0,3, стопа 1,0+-0,25. Штатные SMDIP_W9.53mm KiCad шире
и сдвинуты наружу. Корпус: EL817 6,5 x 4,58, MOC305xS 6,5 x 7,3.

Символы (regulator1.kicad_sym): CH32V006F8P6 — в библиотеках KiCad 10 его нет.
Таблица выводов — CH32V006/005 Datasheet V1.8, табл. 2-1-1 и рис. CH32V006F8P
(файл 2512151727_WCH-CH32V006F8P6_C52753342.pdf в корне проекта):
    1 PD4, 2 PD5, 3 PD6, 4 PD7/PA4, 5 PA1, 6 PA2, 7 VSS, 8 PD0, 9 VDD,
    10 PC0 … 17 PC7, 18 PD1, 19 PD2, 20 PD3.
Вывод 4: PD7 и PA4 соединены внутри корпуса (сноска 4 — оба выходами включать
нельзя), PD7 — вывод сброса RST (сноска 5).

    python3 lib/mklib.py
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.expanduser("~/Proj/1.Project/hw-skills/skills/kicad-schematic/scripts")
sys.path.insert(0, SCRIPTS)

from mksym import make_symbol, make_library   # noqa: E402

SYMLIB = os.path.join(HERE, "regulator1.kicad_sym")


def footprints():
    src = os.path.expanduser("~/Proj/1.Project/hw-skills/skills/kicad-pcb/examples/footprints.py")
    spec = importlib.util.spec_from_file_location("footprints", src)
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    pretty = os.path.join(HERE, "regulator1.pretty")
    os.makedirs(pretty, exist_ok=True)
    out = []
    for poles in (2, 3):
        name = f"TerminalBlock_Golten_GT301-5.0-{poles:02d}P_1x{poles:02d}_P5.00mm"
        out.append(fp.golten_gt301_footprint(os.path.join(pretty, name + ".kicad_mod"), poles))
    for name, pins, body_y, descr, tags in (
            ("SMDIP-4_W9.00mm_Everlight-EL817-S1", 4, 4.58,
             "Оптрон Everlight EL817, выводы опций S/S1; площадки по рекомендации "
             "даташита DPC-0000046 Rev.14, стр. 9", "optocoupler EL817 S1 SMD"),
            ("SMDIP-6_W9.00mm_LiteOn-MOC305xS", 6, 7.3,
             "Оптосимистор Lite-On MOC305xS (S-TA, S-TA1); площадки по рекомендации "
             "даташита DS70-2001-025 Rev.E, разд. 7", "optotriac MOC3052S SMD")):
        out.append(smdip_footprint(fp, os.path.join(pretty, name + ".kicad_mod"),
                                   name, pins, body_y, descr, tags))
    return out


def smdip_footprint(fp, path, name, pins, body_y, descr, tags,
                    row=9.0, pitch=2.54, pad_l=1.3, pad_w=1.5, body_x=6.5):
    """SMD DIP: ряды слева и справа, нумерация против часовой стрелки от 1."""
    smd = '"F.Cu" "F.Paste" "F.Mask"'
    n = pins // 2
    y_top = -(n - 1) * pitch / 2
    pads = []
    for k in range(n):
        pads.append(fp._pad(str(k + 1), "smd", "rect", -row / 2, y_top + k * pitch,
                            pad_l, pad_w, smd))
        pads.append(fp._pad(str(pins - k), "smd", "rect", row / 2, y_top + k * pitch,
                            pad_l, pad_w, smd))

    def r(v):
        return round(v, 3)
    bx, by = body_x / 2, body_y / 2
    sx, sy = bx + 0.11, max(by, -y_top + pad_w / 2) + 0.11      # шёлк — снаружи корпуса
    mx = -row / 2 - pad_l / 2 - 0.45                              # метка вывода 1
    cx = -mx + 0.55                                               # двор с меткой
    cy = max(by, -y_top + pad_w / 2) + 0.25
    ch = 1.0                                                      # срез угла у вывода 1
    text = f'''(footprint "{name}"
	(version 20240108)
	(generator "mklib")
	(layer "F.Cu")
	(descr "{descr}")
	(tags "{tags}")
	(attr smd)
	(fp_text reference "REF**" (at 0 {r(-cy - 1.0)}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
	(fp_text value "{name}" (at 0 {r(cy + 1.0)}) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(fp_text user "${{REFERENCE}}" (at 0 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
	(fp_poly (pts (xy {r(-bx + ch)} {r(-by)}) (xy {r(bx)} {r(-by)}) (xy {r(bx)} {r(by)}) (xy {r(-bx)} {r(by)}) (xy {r(-bx)} {r(-by + ch)})) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))
	(fp_rect (start {r(-sx)} {r(-sy)}) (end {r(sx)} {r(sy)}) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))
	(fp_circle (center {r(mx)} {r(y_top)}) (end {r(mx + 0.2)} {r(y_top)}) (stroke (width 0.12) (type solid)) (fill solid) (layer "F.SilkS"))
	(fp_rect (start {r(-cx)} {r(-cy)}) (end {r(cx)} {r(cy)}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))
{chr(10).join(pads)}
)
'''
    open(path, "w", encoding="utf-8").write(text)
    return path


def symbols():
    io = "bidirectional"
    mcu = make_symbol(
        "CH32V006F8P6",
        [(str(n), f"PC{k}", io, "L") for k, n in enumerate(range(10, 18))] +
        [("8", "PD0", io, "R"), ("18", "PD1", io, "R"), ("19", "PD2", io, "R"),
         ("20", "PD3", io, "R"), ("1", "PD4", io, "R"), ("2", "PD5", io, "R"),
         ("3", "PD6", io, "R"), ("4", "PD7/PA4", io, "R"), ("5", "PA1", io, "R"),
         ("6", "PA2", io, "R"),
         ("9", "VDD", "power_in", "T"),
         ("7", "VSS", "power_in", "B")],
        description="WCH CH32V006F8P6, RISC-V2A 48 MHz, 62K flash, 8K SRAM, VDD 2.0-5.5 V, TSSOP-20",
        keywords="WCH RISC-V MCU CH32V006",
        footprint="Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
        datasheet="${KIPRJMOD}/../2512151727_WCH-CH32V006F8P6_C52753342.pdf",
        ref_prefix="U")
    return make_library(SYMLIB, [mcu])


if __name__ == "__main__":
    for f in footprints():
        print("записано:", f)
    print("записано:", symbols())
