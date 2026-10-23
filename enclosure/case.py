#!/usr/bin/env python3
"""
Корпус одноканального регулятора под плату v2 — модель как код (FreeCAD 1.1).

Запуск из hw_1ch_v2/:
    freecadcmd enclosure/case.py                    # основной, компактный 3 А: build/
    CASE_VARIANT=4A freecadcmd enclosure/case.py    # запасной 4 А (шире на 13 мм): build_4A/
    python3 enclosure/render.py [build_4A]          # картинки

Корпус строится вокруг платы ../regulator1.kicad_pcb: контур, крепёжные
отверстия (круги на Edge.Cuts), клеммники, симистор, IRM-10-5, площадки
проводов и деление деталей на сетевые и низковольтные (по цепям) берутся из
файла платы. Все детали платы — сверху, плата лежит на стойках дна.

Варианты отличаются только радиатором: он стоит в левом нижнем углу между ЖКИ
и клеммниками, и длина его рёбер задаёт ширину корпуса. Остальное одинаково.

Система координат — как у STEP из KiCad: X = x платы, Y = -y платы, Z = 0 на
наружной плоскости дна. Координаты в комментариях и параметрах — в мм платы
(x вправо, y вниз, как в KiCad). Корпус вешается на стену клеммниками вниз:
«верх» для человека — сторона -y платы, то есть вид на крышку совпадает с
видом на плату в KiCad.
"""
import json
import math
import os
import re
import subprocess

import FreeCAD as App
import Import
import MeshPart
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
VARIANT = os.environ.get("CASE_VARIANT", "3A")     # выбор заказчика 2026-10-08 — компактный
BUILD = os.path.join(HERE, "build" if VARIANT == "3A" else "build_" + VARIANT)
PCB_FILE = os.path.join(HW, "regulator1.kicad_pcb")
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
FONT = "DejaVuSans-Bold.ttf"
MODELS_3D = [
    os.environ.get("KICAD10_3DMODEL_DIR", ""),
    "/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Packages3D/x86_64/stable/active/files/3dmodels",
    "/usr/share/kicad/3dmodels",
]

# ---------------------------------------------------------------- корпус
WALL = 2.4          # стенки (6 периметров по 0,4)
FLOOR = 2.0         # дно
LID_T = 2.0         # крышка
GAP = 0.5           # от кромки платы до стенки
CORNER_R = 3.0
LIP_T, LIP_H, LIP_CL = 1.5, 4.0, 0.3   # бортик крышки внутри стенок
VENT_W, VENT_PITCH = 1.6, 4.0          # щели вентиляции: щуп ⌀2,5 не проходит
# Бобышки боковых саморезов крышки: высота 5,4 — над платой ЖКИ (её верх в 6,0 под крышкой).
SIDE_HOLE, SIDE_PILOT, SIDE_BLOCK_W, SIDE_BLOCK_D, SIDE_BLOCK_H = 2.6, 1.8, 7.0, 4.0, 5.4
KEY_HEAD_D, KEY_SLOT_W, KEY_SLOT_L = 8.5, 4.5, 9.0
# Ключевые пазы — под низковольтной частью (под платой там только земля B.Cu):
# центр отверстия под головку; шуруп после навески — на KEY_SLOT_L выше (к -y платы).
KEYS = [(149.0, 121.0), (166.0, 121.0)]
PCB_PILOT, PCB_SCREW_DEPTH, BOSS_R = 2.4, 9.0, 3.0     # плата: ST2,9x9,5 в отверстия ⌀3,2
STANDOFF = 4.5      # низ платы над дном: выводы клеммников 3,5 мм, головки шурупов в пазах 3 мм
LEAD_BELOW = 2.5    # выводы выводных деталей снизу обрезаются до этой длины
SMALL_PILOT = 1.8
HV_CLEAR = 6.0      # сеть и радиатор — низковольтные и доступные части (радиатор — как сетевая деталь: изоляция фланца — одна ступень)
FUNC_CLEAR = 2.5    # радиатор — сетевые части под нулём и нагрузкой (с изолированным фланцем — запас)
LV_CLEAR = 1.0
WIRE_UP = 6.0
RATING = "~230 В  4 А" if VARIANT == "4A" else "~230 В  3 А"

# ---------------------------------------------------------------- детали
BOARD_T = 1.6
# Mean Well IRM-10: 45,7 x 25,4 x 21,5 (лист данных). Корпус модуля — изолирующий
# (компаунд, усиленная изоляция вход-выход), к нему нужен только монтажный зазор.
IRM_L, IRM_W, IRM_H = 45.7, 25.4, 21.5
# Golten GT301-5.0: глубина 7,6, высота 10, ряд выводов в 4,9 мм от лица ввода,
# винт в 3,2 мм от лица, ввод провода 0,8…6,8 мм над платой.
GT_D, GT_H, GT_PIN, GT_SCREW, GT_WIN = 7.6, 10.0, 4.9, 3.2, (0.8, 6.8)
TERM_SLOT_W = 5.0
TERM_TUBE_T = 1.3   # трубка J203 заходит в бортик крышки на 0,1 — без касания граней
TERMS = ("J101", "J102", "J203")
TERM_LABELS = {"J101": ("L", "N"), "J102": ("L'", "N"), "J203": ("+5", "DQ", "GND")}
TERM_TITLES = {"J101": "СЕТЬ", "J102": "НАГРУЗКА", "J203": "ДАТЧИК"}
BARRIER = ("U101", "U102", "PS101")
# TO-220-3_Vertical: спинка фланца y = -3,16 в осях посадочного места, фланец по x
# от -2,58 до 7,67, верх 18,77 над платой, отверстие — 2,8 ниже верха.
TAB_BACK, TAB_X0, TAB_X1, TAB_TOP, TAB_HOLE_DOWN = -3.16, -2.58, 7.67, 18.77, 2.8
# Радиатор на фланце BTA416Y-800C (фланец изолирован, 2500 В): гребёнка, основание на фланце,
# рёбра к левой стенке.
HS_WALL_GAP, HS_LID_GAP, HS_Z0 = 3.0, 3.0, 3.0
HS_BASE_T, HS_FIN_T, HS_FIN_PITCH = 4.0, 1.6, 5.0
HS_FIN_L = {"4A": 30.0, "3A": None}[VARIANT]   # None — сколько даёт ширина под ЖКИ
# Оценка теплового сопротивления: свободная конвекция внутри корпуса и излучение
# (чернёный алюминий). Воздух в корпусе 40 °C, кристалл не горячее 110 °C.
H_CONV, FIN_EFF, H_RAD, T_AIR, TJ_MAX = 7.0, 0.9, 6.0, 40.0, 110.0
RTH_JMB, RTH_MBHS = 1.9, 0.5           # BTA416Y: кристалл-фланец (табл. 5); фланец-радиатор с пастой
# Потери BTA416Y по рис. 10 даташита (bta416y-800c.pdf, максимальные при 150 °C):
# Vo = 1,086 В, Rs = 0,017 Ом -> P = 0,9·Vo·I + Rs·I² ≈ 0,977·I + 0,017·I² (4,2 Вт при 4 А).
# Типовых значений в даташите нет — «обычные» потери приняты равными максимальным.
# Предел кристалла оставлен 110 °C, хотя BTA416Y допускает 150: в пластиковом корпусе
# ограничивает нагрев воздуха и радиатора, а не кристалл.
P_A, P_B, P_TYP = 0.9 * 1.086, 0.017, 1.0
# ЖКИ 1602 с переходником I2C — модель заказчика «LCD 1602 +I2C(+symbols).STEP»
# (enclosure/models/LCD1602_I2C.step); она же идёт в проверки зазоров и в расчёт высоты.
# Оси модели: центр платы ЖКИ, X вправо, Y вверх по тексту, Z к лицу. Размеры сняты разрезами:
# плата ЖКИ 80 x 36,25, z -0,75…0,75; лицо рамки z 8,45; рамка у лица 70,6 x 23,4, у платы
# 71,2 x 24,2, центр рамки на 0,525 ниже центра платы; переходник 41,5 x 19,1 на z -6,95…-5,35;
# ниже всего подстроечник (z -12,35); колодка I2C угловая, штырьки влево до x -38,8.
LCD_MODEL = os.path.join(HERE, "models", "LCD1602_I2C.step")
LCD_W, LCD_H, LCD_PCB_T = 80.0, 36.25, 1.5
LCD_TOP_Z, LCD_PCB_TOP_Z, LCD_BACK_Z = 8.45, 0.75, -3.0   # лицо рамки, верх платы, капли компаунда сзади
LCD_HOLES = (37.5, 15.5)            # отверстия ⌀3,06 через 75 x 31
LCD_BEZEL = (71.0, 23.9)            # рамка в толще крышки
LCD_BEZEL_DY = -0.525               # смещение центра рамки по Y модели
LCD_RECESS = 0.3
LCD_HDR_X = (-32.77, 7.88)          # 16-контактная колодка ЖКИ, x от центра
# Провода I2C паяются к угловым штырькам колодки переходника; место под пайку и изгиб
# (x0, x1, y0, y1, z0, z1 в осях модели). Разъём Dupont в корпус не входит.
I2C_WIRES = (-42.0, -38.8, 3.6, 13.3, -11.8, -6.9)
# Выводы подсветки на правом торце ЖКИ (x0, x1, y0, y1, верх z в осях модели) — под ними выемка в бортике.
LCD_BL_TAB = (35.63, 38.80, -5.75, 5.75, 3.75)
# Кнопки L-KLS7-TS6601-7.0-180 в печатном держателе, толкатели в крышке.
SW_BODY, SW_BODY_H, SW_H, SW_PLUNGER_R = 6.0, 3.5, 7.0, 1.75
SW_LEGS, SW_LEG_L = (3.25, 2.25), 3.5
SW_PITCH = 12.5
CAP_R, CAP_HOLE_R, CAP_FLANGE_R, CAP_FLANGE_T, CAP_STEM_R, CAP_STEM_L, CAP_PROUD = \
    5.0, 5.25, 6.0, 1.5, 2.0, 1.5, 2.0
HOLDER_T, HOLDER_BOSS_R, HOLDER_SCREW_DX, HOLDER_END = 2.0, 2.5, 8.5, 11.0
ABS_DENSITY = 1.04

# ---------------------------------------------------------------- чтение платы

def sexp(text):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == "(":
            stack.append([])
        elif t == ")":
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t[1:-1] if t.startswith('"') else t)
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def one(node, key):
    r = find(node, key)
    return r[0] if r else None


def rot_pt(x0, y0, rot, lx, ly):
    """Точка в осях посадочного места -> координаты платы (как в KiCad)."""
    a = math.radians(rot)
    return (x0 + lx * math.cos(a) + ly * math.sin(a), y0 - lx * math.sin(a) + ly * math.cos(a))


class Board:
    def __init__(self, path):
        root = sexp(open(path, encoding="utf-8").read())
        xs, ys = [], []
        self.holes = []
        for g in find(root, "gr_rect") + find(root, "gr_line") + find(root, "gr_circle"):
            if one(g, "layer")[1] != "Edge.Cuts":
                continue
            if g[0] == "gr_circle":
                c, e = one(g, "center"), one(g, "end")
                r = math.hypot(float(e[1]) - float(c[1]), float(e[2]) - float(c[2]))
                self.holes.append((float(c[1]), float(c[2]), 2 * r))
                continue
            for k in ("start", "end"):
                e = one(g, k)
                xs.append(float(e[1]))
                ys.append(float(e[2]))
        self.x0, self.x1, self.y0, self.y1 = min(xs), max(xs), min(ys), max(ys)
        self.fp = {}
        for f in find(root, "footprint"):
            at = one(f, "at")
            x, y = float(at[1]), float(at[2])
            rot = float(at[3]) if len(at) > 3 else 0.0
            ref = next((p[2] for p in find(f, "property") if p[1] == "Reference"), "")
            pads = []
            for p in find(f, "pad"):
                pa = one(p, "at")
                net = one(p, "net")
                pads.append((p[1],) + rot_pt(x, y, rot, float(pa[1]), float(pa[2])) + (net[1] if net else "",))
            cx, cy = [], []
            for g in find(f, "fp_line") + find(f, "fp_rect") + find(f, "fp_circle") + find(f, "fp_poly"):
                ly = one(g, "layer")
                if not (ly and "CrtYd" in ly[1]):
                    continue
                if g[0] == "fp_circle":
                    c, e = one(g, "center"), one(g, "end")
                    r = math.hypot(float(e[1]) - float(c[1]), float(e[2]) - float(c[2]))
                    pts = [(float(c[1]) + dx, float(c[2]) + dy) for dx in (-r, r) for dy in (-r, r)]
                elif g[0] == "fp_poly":
                    pts = [(float(p[1]), float(p[2])) for p in find(one(g, "pts"), "xy")]
                else:
                    pts = [(float(one(g, k)[1]), float(one(g, k)[2])) for k in ("start", "end")]
                for lx, ly_ in pts:
                    px, py = rot_pt(x, y, rot, lx, ly_)
                    cx.append(px)
                    cy.append(py)
            crt = (min(cx), max(cx), min(cy), max(cy)) if cx else None
            self.fp[ref] = dict(name=f[1], x=x, y=y, rot=rot, pads=pads, crt=crt)
        nets = {ref: {p[3] for p in f["pads"] if p[3]} for ref, f in self.fp.items()}
        self.mains_nets = set(nets.get("J101", ()))
        grown = True
        while grown:
            grown = False
            for ref, ns in nets.items():
                if ref not in BARRIER and ns & self.mains_nets and not ns <= self.mains_nets:
                    self.mains_nets |= ns
                    grown = True
        self.mains_refs = {ref for ref, ns in nets.items() if ns & self.mains_nets}


# ---------------------------------------------------------------- примитивы в координатах платы

def kbox(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, -y1, z0))


def kcyl(x, y, r, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(x, -y, z0))


def kcone(x, y, r0, r1, z0, z1):
    return Part.makeCone(r0, r1, z1 - z0, V(x, -y, z0))


def khcyl(x, y, z, r, length, d):
    return Part.makeCylinder(r, length, V(x, -y, z), V(d[0], -d[1], 0))


def kround(x0, x1, y0, y1, z0, z1, r):
    b = kbox(x0, x1, y0, y1, z0, z1)
    edges = [e for e in b.Edges if abs(abs(e.tangentAt(e.FirstParameter).z) - 1) < 1e-9]
    return b.makeFillet(r, edges)


def kstadium(xa, ya, xb, yb, r, z0, z1):
    s = kcyl(xa, ya, r, z0, z1).fuse(kcyl(xb, yb, r, z0, z1))
    if abs(xa - xb) > 1e-6:
        s = s.fuse(kbox(min(xa, xb), max(xa, xb), ya - r, ya + r, z0, z1))
    elif abs(ya - yb) > 1e-6:
        s = s.fuse(kbox(xa - r, xa + r, min(ya, yb), max(ya, yb), z0, z1))
    return s


def fuse(shapes):
    shapes = [s for s in shapes if s is not None]
    r = shapes[0]
    if len(shapes) > 1:
        r = r.fuse(shapes[1:])
    return r.removeSplitter()


def text_solid(s, size, x, y, z_top, depth):
    """Надпись для гравировки на лице крышки, читается при виде на лицо (верх = -y платы)."""
    chars = Part.makeWireString(s, FONT_DIR, FONT, size, 0)
    faces = []
    for ch in chars:
        if not ch:
            continue
        polys = []
        for w in ch:
            pts = w.discretize(Deflection=0.01)
            if len(pts) > 2:
                if (pts[0] - pts[-1]).Length > 1e-6:
                    pts.append(pts[0])
                polys.append(Part.makePolygon(pts))
        faces.append(Part.makeFace(polys, "Part::FaceMakerBullseye"))
    if not faces:
        return None
    comp = Part.makeCompound(faces)
    bb = comp.BoundBox
    comp.translate(V(x - (bb.XMin + bb.XMax) / 2, -y - (bb.YMin + bb.YMax) / 2, z_top - depth))
    return comp.extrude(V(0, 0, depth + 0.3))


def text_halfwidth(s, size):
    return 0.42 * size * len(s)


def overlap(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


# ---------------------------------------------------------------- компоновка

class Term:
    """Клеммник GT301: положение, лицо ввода, винты."""

    def __init__(self, ref, x, y, rot, n):
        self.ref, self.x, self.y, self.rot, self.n = ref, x, y, rot, n
        a = math.radians(rot)
        self.dir = (round(math.sin(a), 6), round(math.cos(a), 6))
        self.poles = [rot_pt(x, y, rot, 5.0 * k, 0) for k in range(n)]
        self.screws = [rot_pt(x, y, rot, 5.0 * k, GT_PIN - GT_SCREW) for k in range(n)]
        pts = [rot_pt(x, y, rot, lx, ly) for lx in (-2.5, 5.0 * n - 2.5) for ly in (GT_PIN - GT_D, GT_PIN)]
        self.box = (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
        r = TERM_SLOT_W / 2 + TERM_TUBE_T
        xs = [p[0] for p in self.screws]
        ys = [p[1] for p in self.screws]
        self.tube = (min(xs) - r, max(xs) + r, min(ys) - r, max(ys) + r)


def heatsink_fins(z0, z1):
    n = max(2, int((z1 - z0 - HS_FIN_T) / HS_FIN_PITCH) + 1)
    step = (z1 - z0 - HS_FIN_T) / (n - 1)
    return [z0 + k * step for k in range(n)]


def heatsink_rth(hs):
    """Тепловое сопротивление гребёнки, К/Вт: конвекция по всей площади рёбер и основания,
    излучение — по огибающей (рёбра смотрят друг на друга)."""
    x0, x1, y0, y1, z0, z1 = hs
    lf, ly, lz = x1 - x0 - HS_BASE_T, y1 - y0, z1 - z0
    n = len(heatsink_fins(z0, z1))
    a_conv = (2 * n * lf * ly + 2 * ly * lz + 2 * lz * HS_BASE_T) * 1e-6
    a_env = (2 * (x1 - x0) * ly + 2 * (x1 - x0) * lz + ly * lz) * 1e-6
    return 1.0 / (H_CONV * FIN_EFF * a_conv + H_RAD * a_env)


def current_for_power(p):
    """Ток, при котором потери симистора по максимальной кривой равны p."""
    return (-P_A + math.sqrt(P_A ** 2 + 4 * P_B * p)) / (2 * P_B)


class Layout:
    def __init__(self, B, warn):
        self.B = B
        self.z_bb = FLOOR + STANDOFF
        self.z_bt = self.z_bb + BOARD_T
        q = B.fp["Q101"]
        nx, ny = rot_pt(0, 0, q["rot"], 0, -1)
        if abs(nx + 1) > 1e-6 or abs(ny) > 1e-6:
            raise SystemExit("Q101: фланец должен смотреть в -x платы — компоновка рассчитана на это")
        self.tab_x = rot_pt(q["x"], q["y"], q["rot"], 0, TAB_BACK)[0]
        self.tab_y = sorted(rot_pt(q["x"], q["y"], q["rot"], lx, 0)[1] for lx in (TAB_X0, TAB_X1))
        self.tab_hole = (self.tab_x, rot_pt(q["x"], q["y"], q["rot"], 2.54, 0)[1], self.z_bt + TAB_TOP - TAB_HOLE_DOWN)
        self.terms = []
        for ref in TERMS:
            f = B.fp[ref]
            t = Term(ref, f["x"], f["y"], f["rot"], len(f["pads"]))
            if t.dir != (0, 1) or abs(t.box[3] - B.y1) > 0.6:
                raise SystemExit(f"{ref}: лицо ввода провода должно стоять на нижней кромке платы (y = {B.y1})")
            self.terms.append(t)
        self.xin1 = B.x1 + GAP
        self.yin0 = B.y0 - GAP
        self.yin1 = B.y1 + GAP
        # ширина: рёбра радиатора к левой стенке; не меньше, чем нужно ЖКИ с проводами I2C
        over = -I2C_WIRES[0] - LCD_W / 2                  # провода I2C левее края ЖКИ
        lcd_need = LCD_W + over + 2 * LIP_CL + 0.5
        x0_lcd = self.xin1 - lcd_need
        if HS_FIN_L is None:
            self.xin0 = min(x0_lcd, B.x0 - GAP)
        else:
            self.xin0 = min(x0_lcd, B.x0 - GAP, self.tab_x - HS_BASE_T - HS_FIN_L - HS_WALL_GAP)
        self.xo0, self.xo1 = self.xin0 - WALL, self.xin1 + WALL
        self.yo0, self.yo1 = self.yin0 - WALL, self.yin1 + WALL
        # ЖКИ — у верхней стенки, по центру корпуса вместе с проводами I2C (они слева)
        self.lcd_cx = (self.xin0 + self.xin1) / 2 + over / 2
        self.lcd_y0 = self.yin0 + LIP_CL
        self.lcd_y1 = self.lcd_y0 + LCD_H
        self.lcd_cy = (self.lcd_y0 + self.lcd_y1) / 2
        self.r_lcd = (self.lcd_cx - LCD_W / 2, self.lcd_cx + LCD_W / 2, self.lcd_y0, self.lcd_y1)
        if self.lcd_cx + I2C_WIRES[0] < self.xin0 + LIP_CL + 0.2 or self.r_lcd[1] > self.xin1 - LIP_CL:
            raise SystemExit("ЖКИ с переходником не входит между стенками")
        self.bezel_c = (self.lcd_cx, self.lcd_cy - LCD_BEZEL_DY)   # центр рамки в мм платы
        # радиатор: от стенки до фланца; по y — от ЖКИ (6 мм) до клеммников сети (2,5 мм)
        y_lo = self.lcd_y1 + HV_CLEAR
        y_hi = min(t.box[2] for t in self.terms if t.ref in ("J101", "J102")) - FUNC_CLEAR
        self.hs_xy = (self.xin0 + HS_WALL_GAP, self.tab_x, y_lo, y_hi)
        if not (y_lo <= self.tab_y[0] and self.tab_y[1] <= y_hi):
            raise SystemExit("радиатор не накрывает фланец Q101 по y")
        # IRM-10: коробка по центру его места на плате
        x0, x1, y0, y1 = B.fp["PS101"]["crt"]
        self.irm_c = ((x0 + x1) / 2, (y0 + y1) / 2)
        cx, cy = self.irm_c
        self.irm = (cx - IRM_L / 2, cx + IRM_L / 2, cy - IRM_W / 2, cy + IRM_W / 2)
        # кнопки: ряд над IRM, правее радиатора на HV_CLEAR
        x1b = self.tab_x + HV_CLEAR + HOLDER_END + 0.5
        yb = cy
        self.btn = [(x1b + SW_PITCH * k, yb) for k in range(3)]
        self.holder = (x1b - HOLDER_END, self.btn[2][0] + HOLDER_END, yb - 5.0, yb + 5.0)
        self.holder_screws = [(x1b - HOLDER_SCREW_DX, yb), (self.btn[2][0] + HOLDER_SCREW_DX, yb)]
        if self.holder[1] > self.xin1 - LIP_CL - LIP_T:
            raise SystemExit("держатель кнопок упирается в правую стенку")
        # саморезы крышки: слева и справа — на 10 мм выше центра ЖКИ: между верхними стойками ЖКИ
        # и выводами подсветки на правом торце модуля (y ±5,75, до 3 мм под крышкой);
        # сверху — правее колодки ЖКИ; снизу — между трубками клеммников сети и датчика
        j_mains = max(t.tube[1] for t in self.terms if t.ref in ("J101", "J102"))
        j_lv = min(t.tube[0] for t in self.terms if t.ref == "J203")
        y0_x = max(self.lcd_cx + LCD_HDR_X[1] + 1.27 + 1.0 + SIDE_BLOCK_W / 2, self.lcd_cx + 20.0)
        self.side = [("x0", self.lcd_cy - 10.0), ("x1", self.lcd_cy - 10.0), ("y0", y0_x), ("y1", (j_mains + j_lv) / 2)]
        self.keys = KEYS
        self.d_lcd = LCD_TOP_Z + LCD_RECESS - LID_T - LCD_BACK_Z    # низ ЖКИ без переходника под крышкой
        self.d_btn = CAP_FLANGE_T + CAP_STEM_L + SW_H + 1.0 + (SW_LEG_L - 1.0)

    def set_height(self, h):
        self.h = h
        self.z_li = self.z_bt + h
        self.z_lo = self.z_li + LID_T
        self.lcd_pcb_top = self.z_lo - LCD_RECESS - (LCD_TOP_Z - LCD_PCB_TOP_Z)
        self.z_cap_flange = self.z_li - CAP_FLANGE_T
        self.z_tip = self.z_cap_flange - CAP_STEM_L
        self.z_sw = self.z_tip - SW_H
        self.z_hb = self.z_sw - 1.0
        x0, x1, y0, y1 = self.hs_xy
        self.hs = (x0, x1, y0, y1, self.z_bt + HS_Z0, self.z_li - HS_LID_GAP)
        self.z_side = self.z_li - SIDE_BLOCK_H / 2


DEPTH_CELL = 0.5


def depth_map(L, items):
    """Карта глубин того, что висит на крышке (ЖКИ с переходником, провода I2C, кнопки):
    для каждой клетки 0,5 x 0,5 мм в плане — насколько ниже внутренней плоскости крышки
    опускается деталь. От высоты корпуса не зависит: всё крепится к крышке."""
    import numpy as np
    nx = int((L.xin1 - L.xin0) / DEPTH_CELL) + 2
    ny = int((L.yin1 - L.yin0) / DEPTH_CELL) + 2
    D = np.full((ny, nx), -1e9)
    who = np.full((ny, nx), -1, dtype=int)
    for k, (name, shape) in enumerate(items):
        pts, tris = shape.tessellate(0.2)
        if not tris:
            continue
        P = np.array([(p.x, -p.y, p.z) for p in pts])
        T = np.array(tris)
        X, Y, Z = P[T, 0], P[T, 1], P[T, 2]
        ix0 = np.clip(((X.min(1) - L.xin0) / DEPTH_CELL).astype(int), 0, nx - 1)
        ix1 = np.clip(((X.max(1) - L.xin0) / DEPTH_CELL).astype(int), 0, nx - 1)
        iy0 = np.clip(((Y.min(1) - L.yin0) / DEPTH_CELL).astype(int), 0, ny - 1)
        iy1 = np.clip(((Y.max(1) - L.yin0) / DEPTH_CELL).astype(int), 0, ny - 1)
        dep = L.z_li - Z.min(1)
        for a, b, c, d, v in zip(ix0, ix1, iy0, iy1, dep):
            blk = D[c:d + 1, a:b + 1]
            m = blk < v
            if m.any():
                blk[m] = v
                who[c:d + 1, a:b + 1][m] = k
    return D, who


def required_height(L, comps, items):
    """Высота от платы до крышки — по каждой детали платы и карте глубин деталей на крышке:
    до сетевых — HV_CLEAR в пространстве, до остальных — LV_CLEAR."""
    import numpy as np
    D, who = depth_map(L, items)
    ny, nx = D.shape
    xs = L.xin0 + (np.arange(nx) + 0.5) * DEPTH_CELL
    ys = L.yin0 + (np.arange(ny) + 0.5) * DEPTH_CELL
    req = [(TAB_TOP + HS_LID_GAP, "Q101: верх фланца + зазор радиатора до крышки")]
    for name, s, cls in comps:
        if cls == "pcb":
            continue
        bb = s.BoundBox
        top = bb.ZMax - L.z_bt
        if top <= 0:
            continue
        req.append((top + 1.0, f"крышка над {name}"))
        clr = HV_CLEAR if cls == "mains" else LV_CLEAR
        x0, x1, y0, y1 = bb.XMin, bb.XMax, -bb.YMax, -bb.YMin
        cx = (xs >= x0 - clr) & (xs <= x1 + clr)
        cy = (ys >= y0 - clr) & (ys <= y1 + clr)
        if not cx.any() or not cy.any():
            continue
        sub = D[np.ix_(cy, cx)]
        dx = np.maximum(np.maximum(x0 - xs[cx], xs[cx] - x1), 0)
        dy = np.maximum(np.maximum(y0 - ys[cy], ys[cy] - y1), 0)
        dxy = np.hypot(dy[:, None], dx[None, :]) - DEPTH_CELL * 0.71     # клетка — не точка
        gap = np.sqrt(np.clip(clr ** 2 - np.maximum(dxy, 0) ** 2, 0, None))
        need = np.where((dxy < clr) & (sub > -1e8), top + gap + sub, -1e9)
        i = np.unravel_index(np.argmax(need), need.shape)
        if need[i] > 0:
            k = who[np.ix_(cy, cx)][i]
            kind = {"mains": "сеть", "lv": "НН", "module": "модуль"}[cls]
            req.append((float(need[i]), f"{items[k][0]} над {name} ({top:.1f} мм, {kind})"))
    req.sort(reverse=True)
    return math.ceil(req[0][0] * 10) / 10, req


# ---------------------------------------------------------------- основание

def wall_screw(L, wall, s, z, r, inner, outer):
    if wall == "x0":
        return khcyl(L.xin0 - outer, s, z, r, inner + outer, (1, 0))
    if wall == "x1":
        return khcyl(L.xin1 + outer, s, z, r, inner + outer, (-1, 0))
    if wall == "y0":
        return khcyl(s, L.yin0 - outer, z, r, inner + outer, (0, 1))
    return khcyl(s, L.yin1 + outer, z, r, inner + outer, (0, -1))


def build_base(L):
    B = L.B
    body = kround(L.xo0, L.xo1, L.yo0, L.yo1, 0, L.z_li, CORNER_R)
    body = body.cut(kbox(L.xin0, L.xin1, L.yin0, L.yin1, FLOOR, L.z_li + 1))
    add = []
    for hx, hy, _ in B.holes:
        add.append(kcyl(hx, hy, BOSS_R, FLOOR - 0.01, L.z_bb))
        rib_top = L.z_bb - 1.5
        for wall, d in (("x1", L.xin1 - hx), ("x0", hx - L.xin0), ("y0", hy - L.yin0), ("y1", L.yin1 - hy)):
            if d < 8:
                if wall == "x1":
                    add.append(kbox(hx, L.xin1 + 0.1, hy - 0.8, hy + 0.8, FLOOR - 0.01, rib_top))
                elif wall == "x0":
                    add.append(kbox(L.xin0 - 0.1, hx, hy - 0.8, hy + 0.8, FLOOR - 0.01, rib_top))
                elif wall == "y0":
                    add.append(kbox(hx - 0.8, hx + 0.8, L.yin0 - 0.1, hy, FLOOR - 0.01, rib_top))
                else:
                    add.append(kbox(hx - 0.8, hx + 0.8, hy, L.yin1 + 0.1, FLOOR - 0.01, rib_top))
    body = fuse([body] + add)

    cut = []
    for hx, hy, _ in B.holes:
        cut.append(kcyl(hx, hy, PCB_PILOT / 2, L.z_bb - PCB_SCREW_DEPTH, L.z_bb + 0.1))
    for wall, s in L.side:
        cut.append(wall_screw(L, wall, s, L.z_side, SIDE_HOLE / 2, 0.5, WALL + 1))
    for kx, ky in L.keys:
        cut.append(kcyl(kx, ky, KEY_HEAD_D / 2, -1, FLOOR + 1))
        cut.append(kstadium(kx, ky, kx, ky - KEY_SLOT_L, KEY_SLOT_W / 2, -1, FLOOR + 1))
    # окна под провода клеммников в нижней стенке
    z0, z1 = L.z_bt + GT_WIN[0], L.z_bt + GT_WIN[1]
    for t in L.terms:
        for px, py in t.poles:
            cut.append(kbox(px - 2.1, px + 2.1, L.yin1 - 0.1, L.yo1 + 1, z0, z1))
    # вентиляция: воздух входит в левую стенку у нижней половины радиатора, проходит
    # вдоль рёбер вверх (к -y платы) и выходит в левую и верхнюю стенки под ЖКИ
    hs = L.hs_xy
    z_lo = (L.z_bt + HS_Z0 + 1.0, L.z_li - HS_LID_GAP - 1.0)          # высота рёбер
    z_hi = (L.z_bt + 1.0, L.z_li - L.d_lcd - 2.0)                      # под ЖКИ
    y = (hs[2] + hs[3]) / 2
    while y + VENT_W / 2 <= L.yin1 - 3.0:
        cut.append(kbox(L.xo0 - 1, L.xin0 + 0.1, y - VENT_W / 2, y + VENT_W / 2, *z_lo))
        y += VENT_PITCH
    y = L.yin0 + 4.0
    while y + VENT_W / 2 <= hs[2] - 4.0:
        cut.append(kbox(L.xo0 - 1, L.xin0 + 0.1, y - VENT_W / 2, y + VENT_W / 2, *z_hi))
        y += VENT_PITCH
    x = L.xin0 + 4.0
    while x + VENT_W / 2 <= L.B.fp["U102"]["crt"][0]:
        cut.append(kbox(x - VENT_W / 2, x + VENT_W / 2, L.yo0 - 1, L.yin0 + 0.1, *z_hi))
        x += VENT_PITCH
    return body.cut(cut).removeSplitter()


# ---------------------------------------------------------------- крышка

def side_block(L, wall, s):
    a, d, w = LIP_CL, SIDE_BLOCK_D, SIDE_BLOCK_W / 2
    z0, z1 = L.z_li - SIDE_BLOCK_H, L.z_li + 0.01
    if wall == "x0":
        return kbox(L.xin0 + a, L.xin0 + a + d, s - w, s + w, z0, z1)
    if wall == "x1":
        return kbox(L.xin1 - a - d, L.xin1 - a, s - w, s + w, z0, z1)
    if wall == "y0":
        return kbox(s - w, s + w, L.yin0 + a, L.yin0 + a + d, z0, z1)
    return kbox(s - w, s + w, L.yin1 - a - d, L.yin1 - a, z0, z1)


def lcd_holes(L):
    return [(L.lcd_cx + sx * LCD_HOLES[0], L.lcd_cy + sy * LCD_HOLES[1]) for sx in (-1, 1) for sy in (-1, 1)]


def build_lid(L):
    add = [kround(L.xo0, L.xo1, L.yo0, L.yo1, L.z_li, L.z_lo, CORNER_R)]
    a, b = LIP_CL, LIP_CL + LIP_T
    frame = kbox(L.xin0 + a, L.xin1 - a, L.yin0 + a, L.yin1 - a, L.z_li - LIP_H, L.z_li + 0.01)
    frame = frame.cut(kbox(L.xin0 + b, L.xin1 - b, L.yin0 + b, L.yin1 - b, L.z_li - LIP_H - 1, L.z_li + 1))
    hx0, hx1, hy0, hy1 = L.hs_xy
    frame = frame.cut(kbox(hx0 - 4, hx1 + 4, hy0 - 4, hy1 + 4, L.z_li - LIP_H - 1, L.z_li + 1))
    tx0, tx1, ty0, ty1, tz = LCD_BL_TAB                       # выемка над выводами подсветки ЖКИ
    z_tab = L.z_lo - LCD_RECESS - (LCD_TOP_Z - tz)
    frame = frame.cut(kbox(L.lcd_cx + tx0 - 0.5, L.xin1, L.lcd_cy - ty1 - 0.5, L.lcd_cy - ty0 + 0.5,
                           L.z_li - LIP_H - 1, z_tab + 0.5))
    add.append(frame)
    for wall, s in L.side:
        add.append(side_block(L, wall, s))
    for hx, hy in lcd_holes(L):
        add.append(kcyl(hx, hy, 2.75, L.lcd_pcb_top, L.z_li + 0.01))
    for hx, hy in L.holder_screws:
        add.append(kcyl(hx, hy, HOLDER_BOSS_R, L.z_hb + HOLDER_T, L.z_li + 0.01))
    clip = kbox(L.xin0 + LIP_CL, L.xin1 - LIP_CL, L.yin0 + LIP_CL, L.yin1 - LIP_CL, 0, 100)
    z_tube = L.z_bt + GT_H + 1.0
    r_out = TERM_SLOT_W / 2 + TERM_TUBE_T
    for t in L.terms:
        (xa, ya), (xb, yb) = t.screws[0], t.screws[-1]
        add.append(kstadium(xa, ya, xb, yb, r_out, z_tube, L.z_li + 0.01).common(clip))
    lid = fuse(add)

    cut = []
    wx, wy = LCD_BEZEL[0] / 2 + 0.2, LCD_BEZEL[1] / 2 + 0.2
    bx, by = L.bezel_c
    cut.append(kbox(bx - wx, bx + wx, by - wy, by + wy, L.z_li - 1, L.z_lo + 1))
    ch, e = 0.8, 1.1

    def rect(dx, z):
        return Part.makePolygon([V(bx - wx - dx, -(by - wy - dx), z), V(bx + wx + dx, -(by - wy - dx), z),
                                 V(bx + wx + dx, -(by + wy + dx), z), V(bx - wx - dx, -(by + wy + dx), z),
                                 V(bx - wx - dx, -(by - wy - dx), z)])
    cut.append(Part.makeLoft([rect(0, L.z_lo - ch), rect(e, L.z_lo + 0.3)], True))
    for hx, hy in lcd_holes(L):
        cut.append(kcyl(hx, hy, SMALL_PILOT / 2, L.lcd_pcb_top - 0.1, L.lcd_pcb_top + 6.0))
    for hx, hy in L.holder_screws:
        cut.append(kcyl(hx, hy, SMALL_PILOT / 2, L.z_hb + HOLDER_T - 0.1, L.z_hb + HOLDER_T + 7.0))
    for wall, s in L.side:
        cut.append(wall_screw(L, wall, s, L.z_side, SMALL_PILOT / 2, LIP_CL + SIDE_BLOCK_D + 0.5, 0.0))
    for bx, by in L.btn:
        cut.append(kcyl(bx, by, CAP_HOLE_R, L.z_li - 1, L.z_lo + 1))
        cut.append(kcone(bx, by, CAP_HOLE_R, CAP_HOLE_R + 0.5, L.z_lo - 0.5, L.z_lo + 0.01))
    r = TERM_SLOT_W / 2
    for t in L.terms:
        (xa, ya), (xb, yb) = t.screws[0], t.screws[-1]
        cut.append(kstadium(xa, ya, xb, yb, r, z_tube - 1, L.z_lo + 1))
        cut.append(kstadium(xa, ya, xb, yb, r + 0.8, L.z_lo - 0.8, L.z_lo + 1))
    cut += labels(L)
    return lid.cut([c for c in cut if c is not None]).removeSplitter()


def labels(L):
    """Надписи на лице. Клеммники внизу: полюса над прорезью, название над полюсами."""
    d, z = 0.5, L.z_lo
    out = []
    for t in L.terms:
        sy = t.screws[0][1]
        names = TERM_LABELS[t.ref]
        size = min(2.4, (5.0 - 0.8) / (0.84 * max(len(n) for n in names)))   # подпись уже шага полюсов
        for (sx, _), nm in zip(t.screws, names):
            out.append(text_solid(nm, size, sx, sy - TERM_SLOT_W / 2 - 0.8 - 2.2, z, d))
        xs = [p[0] for p in t.screws]
        out.append(text_solid(TERM_TITLES[t.ref], 1.8, (min(xs) + max(xs)) / 2, sy - TERM_SLOT_W / 2 - 0.8 - 5.6, z, d))
    # кнопки: подписи над толкателями (между окном ЖКИ и кнопками)
    y_txt = (L.bezel_c[1] + LCD_BEZEL[1] / 2 + 1.0 + L.btn[0][1] - CAP_HOLE_R - 0.5) / 2
    for (bx, by), nm in zip(L.btn, ("МЕНЮ", "−", "+")):
        out.append(text_solid(nm, 2.6 if len(nm) > 1 else 4.0, bx, y_txt, z, d))
    # над радиатором — название и номинал
    hx = (L.hs_xy[0] + L.hs_xy[1]) / 2
    hy = (L.hs_xy[2] + L.hs_xy[3]) / 2 - 3.0
    size = min(3.0, (L.hs_xy[1] - L.hs_xy[0] - 2.0) / (0.84 * len("РЕГУЛЯТОР")))
    out.append(text_solid("РЕГУЛЯТОР", size, hx, hy - 2.2, z, d))
    out.append(text_solid(RATING, min(2.4, size), hx, hy + 2.2, z, d))
    return out


# ---------------------------------------------------------------- кнопки

def build_holder(L):
    x0, x1, y0, y1 = L.holder
    h = kbox(x0, x1, y0, y1, L.z_hb, L.z_hb + HOLDER_T)
    cut = []
    for bx, by in L.btn:
        cut.append(kbox(bx - 3.6, bx + 3.6, by - 3.2, by + 3.2, L.z_hb + 1.0, L.z_hb + HOLDER_T + 1))
        for sx in (-1, 1):
            xl = bx + sx * SW_LEGS[0]
            cut.append(kbox(xl - 0.6, xl + 0.6, by - SW_LEGS[1] - 0.8, by + SW_LEGS[1] + 0.8, L.z_hb - 1, L.z_hb + 2))
    for hx, hy in L.holder_screws:
        cut.append(kcyl(hx, hy, 1.25, L.z_hb - 1, L.z_hb + HOLDER_T + 1))
    return h.cut(cut).removeSplitter()


def build_cap(L, bx, by):
    top = L.z_lo + CAP_PROUD
    parts = [kcyl(bx, by, CAP_R, L.z_li - 0.01, top - 0.6),
             kcone(bx, by, CAP_R, CAP_R - 0.6, top - 0.6, top),
             kcyl(bx, by, CAP_FLANGE_R, L.z_cap_flange, L.z_li),
             kcyl(bx, by, CAP_STEM_R, L.z_tip, L.z_cap_flange + 0.01)]
    return fuse(parts)


# ---------------------------------------------------------------- модели деталей для проверки

def model_switch(bx, by, z):
    parts = [kbox(bx - SW_BODY / 2, bx + SW_BODY / 2, by - SW_BODY / 2, by + SW_BODY / 2, z, z + SW_BODY_H),
             kcyl(bx, by, SW_PLUNGER_R, z + SW_BODY_H - 0.01, z + SW_H)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            lx, ly = bx + sx * SW_LEGS[0], by + sy * SW_LEGS[1]
            parts.append(kbox(lx - 0.35, lx + 0.35, ly - 0.15, ly + 0.15, z - SW_LEG_L, z + 0.5))
    return fuse(parts)


def model_heatsink(L):
    x0, x1, y0, y1, z0, z1 = L.hs
    parts = [kbox(x1 - HS_BASE_T, x1, y0, y1, z0, z1)]
    for zf in heatsink_fins(z0, z1):
        parts.append(kbox(x0, x1 - HS_BASE_T + 0.01, y0, y1, zf, zf + HS_FIN_T))
    hs = fuse(parts)
    hx, hy, hz = L.tab_hole
    return hs.cut(Part.makeCylinder(1.6, HS_BASE_T + 2, V(hx - HS_BASE_T - 1, -hy, hz), V(1, 0, 0)))


def load_lcd_model(warn):
    """Модель ЖКИ с переходником в осях модели; разбор STEP (20 МБ) — полминуты, поэтому
    после первого чтения кладётся в build/ как BREP."""
    cache = os.path.join(BUILD, "lcd_i2c.brep")
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(LCD_MODEL):
        return Part.read(cache)
    if os.path.exists(LCD_MODEL):
        s = Part.read(LCD_MODEL)
        s.exportBrep(cache)
        return s
    warn.append(f"нет модели ЖКИ {LCD_MODEL} — вместо неё коробки по снятым размерам")
    s = Part.makeBox(LCD_W, LCD_H, LCD_PCB_T, V(-LCD_W / 2, -LCD_H / 2, -LCD_PCB_T / 2))
    s = s.fuse(Part.makeBox(LCD_BEZEL[0], LCD_BEZEL[1], LCD_TOP_Z - LCD_PCB_TOP_Z,
                            V(-LCD_BEZEL[0] / 2, LCD_BEZEL_DY - LCD_BEZEL[1] / 2, LCD_PCB_TOP_Z)))
    return s.fuse(Part.makeBox(41.5, 19.1, 12.35 - 0.75, V(-33.2, -1.98, -12.35)))


def model_lcd(L, raw):
    """ЖКИ с переходником на месте: лицо рамки на LCD_RECESS ниже лица крышки; провода I2C."""
    top = L.z_lo - LCD_RECESS
    s = raw.copy()
    s.translate(V(L.lcd_cx, -L.lcd_cy, top - LCD_TOP_Z))
    x0, x1, y0, y1, z0, z1 = I2C_WIRES
    wires = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(L.lcd_cx + x0, -L.lcd_cy + y0, top - LCD_TOP_Z + z0))
    return s, wires


def load_board(L, warn):
    """Плата из KiCad (kicad-cli export step) + модели деталей, которых нет в библиотеке.
    Возвращает [(имя, тело, класс)], класс: pcb / mains / lv / module."""
    B = L.B
    models_dir = next((d for d in MODELS_3D if d and os.path.isdir(d)), "")
    step = os.path.join(BUILD, "board.step")
    env = dict(os.environ, KICAD10_3DMODEL_DIR=models_dir)
    r = subprocess.run(["kicad-cli", "pcb", "export", "step", "--no-dnp", "--subst-models", "-f",
                        "-o", step, PCB_FILE], env=env, capture_output=True, text=True)

    def cls(ref):
        return "mains" if ref in B.mains_refs else "lv"
    comps = []
    if r.returncode != 0 or not os.path.exists(step):
        warn.append("kicad-cli не выгрузил плату в STEP — проверка без 3D-моделей деталей платы")
    else:
        shp = Part.read(step)
        shp.translate(V(0, 0, L.z_bb))
        trim = kbox(B.x0 - 50, B.x1 + 50, B.y0 - 50, B.y1 + 50, L.z_bb - LEAD_BELOW, L.z_bb + 100)
        for sol in shp.Solids:
            bb = sol.BoundBox
            if bb.XLength > 60 and bb.YLength > 60:
                comps.append(("плата", sol, "pcb"))
                continue
            if bb.ZMin < L.z_bb - LEAD_BELOW:
                sol = sol.common(trim)           # выводы снизу обрезаются при монтаже
            cx, cy = (bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2
            best, bd = "?", 1e9
            for ref, f in B.fp.items():
                if f["crt"] is None:
                    continue
                x0, x1, y0, y1 = f["crt"]
                d = math.hypot(max(x0 - cx, 0, cx - x1), max(y0 - cy, 0, cy - y1))
                if d < bd:
                    best, bd = ref, d
            comps.append((best, sol, cls(best)))
    # IRM-10-5 — модель из energosint (lib/3d/IRM-10.step): корпус — изолирующий модуль,
    # выводы — по цепям площадок (AC — сеть, DC — НН)
    irm = []
    for k, (name, sol, c) in enumerate(comps):
        if name != "PS101":
            continue
        bb = sol.BoundBox
        if bb.XLength < 2.0 and bb.YLength < 2.0:
            px, py = (bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2
            net = min(B.fp["PS101"]["pads"], key=lambda p: math.hypot(p[1] - px, p[2] - py))[3]
            c = "mains" if net in B.mains_nets else "lv"
            comps[k] = (f"PS101 вывод {'AC' if c == 'mains' else 'DC'}", sol, c)
        else:
            comps[k] = ("PS101", sol, "module")
        irm.append(k)
    if not irm:
        warn.append("в STEP платы нет модели IRM-10 — коробка по даташиту")
        x0, x1, y0, y1 = L.irm
        comps.append(("PS101", kbox(x0, x1, y0, y1, L.z_bt, L.z_bt + IRM_H), "module"))
    for t in L.terms:
        x0, x1, y0, y1 = t.box
        comps.append((t.ref, kbox(x0, x1, y0, y1, L.z_bt, L.z_bt + GT_H), cls(t.ref)))
        for px, py in t.poles:
            comps.append((t.ref, kcyl(px, py, 0.5, L.z_bb - 3.5, L.z_bb), cls(t.ref)))
    # предохранитель 372 (TR5): ⌀8,5 x 8 — модели в библиотеке нет
    x0, x1, y0, y1 = B.fp["F101"]["crt"]
    comps.append(("F101", kcyl((x0 + x1) / 2, (y0 + y1) / 2, 4.25, L.z_bt, L.z_bt + 8.0), "mains"))
    # оптроны SMDIP: корпус — изоляция (путь 7,7 мм между рядами выводов), высота 4,0;
    # выводы стороны сети — сетевые, стороны МК — НН
    for ref, (w, h) in (("U101", (4.6, 6.5)), ("U102", (7.3, 6.5))):
        f = B.fp[ref]
        comps.append((ref, kbox(f["x"] - h / 2, f["x"] + h / 2, f["y"] - w / 2, f["y"] + w / 2, L.z_bt, L.z_bt + 4.0), "module"))
        for _, px, py, net in f["pads"]:
            c = "mains" if net in B.mains_nets else "lv"
            comps.append((f"{ref} вывод {'сеть' if c == 'mains' else 'НН'}",
                          kbox(px - 0.65, px + 0.65, py - 0.75, py + 0.75, L.z_bt, L.z_bt + 2.0), c))
    for ref in ("J202", "J204"):
        for _, px, py, _n in B.fp[ref]["pads"]:
            comps.append((ref + " провод", kcyl(px, py, 0.85, L.z_bt, L.z_bt + WIRE_UP), "lv"))
    return comps, models_dir


# ---------------------------------------------------------------- проверки

def interferences(parts, comps):
    rows = []
    for pn, ps in parts:
        pb = ps.BoundBox
        for cn, cs in comps:
            if not pb.intersect(cs.BoundBox):
                continue
            v = ps.common(cs).Volume
            if v > 0.01:
                rows.append((pn, cn, v))
    return rows


def min_dist(a_list, b_list):
    out = {}
    for bn, bs in b_list:
        for an, as_ in a_list:
            d = as_.distToShape(bs)[0]
            if bn not in out or d < out[bn][0]:
                out[bn] = (d, an)
    return out


# ---------------------------------------------------------------- выгрузка

def stl(shape, path):
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.15, Relative=False)
    m.write(path)
    return m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections()


def dump_meshes(path, objs, tol=0.05):
    import numpy as np
    names, colors, groups, vs, ts, voff, toff = [], [], [], [], [], [0], [0]
    for nm, shape, color, grp in objs:
        if shape is None or shape.isNull():
            continue
        pts, tris = shape.tessellate(tol)
        if not tris:
            continue
        vs.append(np.array([(p.x, p.y, p.z) for p in pts], dtype=np.float32))
        ts.append(np.array(tris, dtype=np.int32))
        names.append(nm)
        colors.append(color)
        groups.append(grp)
        voff.append(voff[-1] + len(pts))
        toff.append(toff[-1] + len(tris))
    np.savez_compressed(path, names=np.array(names), groups=np.array(groups), colors=np.array(colors, dtype=np.float32),
                        V=np.concatenate(vs), T=np.concatenate(ts), voff=np.array(voff), toff=np.array(toff))


def main():
    os.makedirs(BUILD, exist_ok=True)
    warn = []
    B = Board(PCB_FILE)
    L = Layout(B, warn)
    print(f"вариант {VARIANT}; плата {B.x1 - B.x0:.1f} x {B.y1 - B.y0:.1f} мм, отверстий {len(B.holes)}")
    comps, models_dir = load_board(L, warn)
    lcd_raw = load_lcd_model(warn)
    L.set_height(60.0)                    # предварительно: карта глубин считается от крышки
    lcd0, wires0 = model_lcd(L, lcd_raw)
    hang = [("ЖКИ с переходником", lcd0), ("провода I2C", wires0), ("держатель кнопок", build_holder(L))] + \
           [(f"кнопка {k + 1}", model_switch(bx, by, L.z_sw)) for k, (bx, by) in enumerate(L.btn)]
    h, req = required_height(L, comps, hang)
    L.set_height(h)
    base = build_base(L)
    lid = build_lid(L)
    holder = build_holder(L)
    caps = [build_cap(L, bx, by) for bx, by in L.btn]
    print("детали корпуса построены:", all(s.isValid() for s in [base, lid, holder] + caps))

    lcd, wires = model_lcd(L, lcd_raw)
    hs = model_heatsink(L)
    switches = [model_switch(bx, by, L.z_sw) for bx, by in L.btn]
    lv_items = [("ЖКИ с переходником", lcd), ("провода I2C", wires), ("держатель кнопок", holder)] + \
               [(f"кнопка {k + 1}", s) for k, s in enumerate(switches)]
    screws = [(f"саморез крышки {w} {s:.0f}", wall_screw(L, w, s, L.z_side, 1.1, LIP_CL + SIDE_BLOCK_D - 0.6, WALL))
              for w, s in L.side]
    screws += [(f"шуруп в пазу ({kx:.0f}; {ky - KEY_SLOT_L:.0f})", fuse([kcyl(kx, ky - KEY_SLOT_L, 2.0, -5, FLOOR),
                                                                      kcyl(kx, ky - KEY_SLOT_L, 4.0, FLOOR, FLOOR + 3.0)]))
               for kx, ky in L.keys]
    screws += [(f"саморез ЖКИ ({x:.0f}; {y:.0f})", kcyl(x, y, 1.1, L.lcd_pcb_top - 2.0, L.lcd_pcb_top + 6.0))
               for x, y in lcd_holes(L)]
    all_comps = [(n, s) for n, s, c in comps] + [("радиатор", hs)] + lv_items[:2] + lv_items[3:]

    parts = [("основание", base), ("крышка", lid), ("держатель кнопок", holder)] + \
            [(f"толкатель {k + 1}", c) for k, c in enumerate(caps)]
    hits = interferences(parts, all_comps)
    hits += interferences([("крышка", lid)], [("основание", base), ("держатель кнопок", holder)] +
                          [(f"толкатель {k + 1}", c) for k, c in enumerate(caps)])
    hits += interferences([("основание", base)], [("держатель кнопок", holder)] +
                          [(f"толкатель {k + 1}", c) for k, c in enumerate(caps)])
    hits += [(a, b, v) for a, b, v in interferences([("радиатор", hs)], [(n, s) for n, s, c in comps if n != "Q101"])]
    mains = [(n, s) for n, s, c in comps if c == "mains"] + [("радиатор", hs)]
    near = lv_items + screws + [(n, s) for n, s, c in comps if c == "lv" and n in ("J203", "J202 провод", "J204 провод")]
    clr = min_dist(mains, near)
    # радиатор — до сетевых деталей под нулём и нагрузкой (клеммники, варистор); с изолированным
    # фланцем радиатор не под фазой, проверка оставлена как запас
    func = min_dist([("радиатор", hs)], [(n, s) for n, s, c in comps if n in ("J101", "J102", "RV101")])

    rth = heatsink_rth(L.hs)
    p_max = (TJ_MAX - T_AIR) / (rth + RTH_JMB + RTH_MBHS)
    i_worst = current_for_power(p_max)
    i_typ = current_for_power(p_max / P_TYP)

    W, Hh = L.xo1 - L.xo0, L.yo1 - L.yo0
    vols = {"основание": base.Volume, "крышка": lid.Volume, "держатель кнопок": holder.Volume,
            "толкатели, 3 шт.": sum(c.Volume for c in caps)}
    rep = [f"Корпус регулятора, плата v2, вариант {VARIANT} — отчёт сборки (enclosure/case.py)\n"]
    rep.append(f"Габарит: {W:.1f} x {Hh:.1f} x {L.z_lo:.1f} мм (без толкателей; они выступают на {CAP_PROUD:.1f})")
    rep.append(f"Внутри: {L.xin1 - L.xin0:.1f} x {L.yin1 - L.yin0:.1f} мм; низ платы {L.z_bb:.1f}, верх {L.z_bt:.1f}, "
               f"крышка изнутри {L.z_li:.1f} мм от дна снаружи")
    rep.append(f"Высота над платой {h:.1f} мм. Что её задаёт:")
    rep += [f"  {v:5.1f}  {why}" for v, why in req[:6]]
    rep.append(f"ЖКИ: центр ({L.lcd_cx:.2f}; {L.lcd_cy:.2f}) в мм платы; кнопки: "
               + ", ".join(f"({x:.1f}; {y:.1f})" for x, y in L.btn))
    x0, x1, y0, y1, z0, z1 = L.hs
    rep.append(f"Радиатор: x {x0:.2f}…{x1:.2f} ({x1 - x0:.1f}, рёбра {x1 - x0 - HS_BASE_T:.1f}), "
               f"y {y0:.2f}…{y1:.2f} ({y1 - y0:.1f}), над платой {z0 - L.z_bt:.1f}…{z1 - L.z_bt:.1f} ({z1 - z0:.1f}) мм, "
               f"рёбер {len(heatsink_fins(z0, z1))}; отверстие фланца {L.tab_hole[2] - L.z_bt:.2f} мм над платой")
    rep.append(f"  оценка Rth радиатора ≈ {rth:.1f} К/Вт; при воздухе в корпусе {T_AIR:.0f} °C и кристалле "
               f"≤ {TJ_MAX:.0f} °C отводится {p_max:.1f} Вт: ток до {i_typ:.1f} А (обычные потери), "
               f"{i_worst:.1f} А (максимальные по даташиту)")
    rep.append("Саморезы крышки (стенка, положение): " + ", ".join(f"{w} {s:.1f}" for w, s in L.side))
    rep.append("Ключевые пазы (головка → шуруп): " + ", ".join(f"({kx:.1f}; {ky:.1f}) → ({kx:.1f}; {ky - KEY_SLOT_L:.1f})"
                                                           for kx, ky in L.keys))
    rep.append("\nПредупреждения:" if warn else "\nПредупреждений нет")
    rep += ["  " + w for w in warn]
    rep.append("\nПересечения (объём > 0,01 мм³):")
    rep += [f"  {a} x {b}: {v:.2f} мм³" for a, b, v in hits] or ["  нет"]
    rep.append(f"\nЗазоры от сетевых деталей и радиатора до низковольтных и доступных (нужно ≥ {HV_CLEAR:.0f} мм):")
    for nm, (d, frm) in sorted(clr.items(), key=lambda kv: kv[1][0]):
        rep.append(f"  {nm}: {d:.2f} мм (от {frm}){'  << МАЛО' if d < HV_CLEAR - 1e-6 else ''}")
    rep.append(f"\nРадиатор — сетевые детали под нулём и нагрузкой (запас, фланец изолирован; нужно ≥ {FUNC_CLEAR:.1f} мм):")
    for nm, (d, _f) in sorted(func.items(), key=lambda kv: kv[1][0]):
        rep.append(f"  {nm}: {d:.2f} мм{'  << МАЛО' if d < FUNC_CLEAR - 1e-6 else ''}")
    rep.append(f"  радиатор — стенка основания: {hs.distToShape(base)[0]:.2f} мм; — крышка: {hs.distToShape(lid)[0]:.2f} мм")
    rep.append("\nМасса печатных деталей (ABS, сплошная печать):")
    for nm, v in vols.items():
        rep.append(f"  {nm}: {v / 1000:.1f} см³ ≈ {v / 1000 * ABS_DENSITY:.0f} г")
    tot = sum(vols.values()) / 1000
    rep.append(f"  всего: {tot:.1f} см³ ≈ {tot * ABS_DENSITY:.0f} г")
    rep.append(f"  радиатор-гребёнка из модели (алюминий): {hs.Volume / 1000:.1f} см³ ≈ {hs.Volume / 1000 * 2.7:.0f} г")
    text = "\n".join(rep)

    def on_bed(shape, flip):
        s = shape.copy()
        if flip:
            s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
        bb = s.optimalBoundingBox()
        s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
        return s
    printed = [("base", base, False), ("lid", lid, True), ("button_holder", holder, False), ("button_cap", caps[0], True)]
    stl_rep = []
    for nm, s, flip in printed:
        ok = stl(on_bed(s, flip), os.path.join(BUILD, nm + ".stl"))
        stl_rep.append(f"  {nm}.stl: {'замкнутая сетка без самопересечений' if ok else 'СЕТКА С ДЕФЕКТАМИ'}")
    text += "\n\nSTL:\n" + "\n".join(stl_rep)
    print(text)
    open(os.path.join(BUILD, "check.txt"), "w", encoding="utf-8").write(text + "\n")

    doc = App.newDocument("case")
    objs = []
    for nm, s in [("base", base), ("lid", lid), ("button_holder", holder)] + [(f"button_cap_{k + 1}", c) for k, c in enumerate(caps)]:
        o = doc.addObject("Part::Feature", nm)
        o.Shape = s
        objs.append(o)
    Import.export(objs, os.path.join(BUILD, "case.step"))
    extra = []
    for nm, s in [("heatsink", hs), ("lcd_i2c", lcd), ("i2c_wires", wires)] + [(f"switch_{k + 1}", s) for k, s in enumerate(switches)]:
        o = doc.addObject("Part::Feature", nm)
        o.Shape = s
        extra.append(o)
    bo = doc.addObject("Part::Feature", "board")
    bo.Shape = Part.makeCompound([s for _, s, _c in comps])
    Import.export(objs + extra + [bo], os.path.join(BUILD, "assembly.step"))

    C = dict(base=(0.80, 0.82, 0.86), lid=(0.70, 0.74, 0.80), cap=(0.25, 0.27, 0.30), holder=(0.95, 0.75, 0.30),
             pcb=(0.12, 0.42, 0.22), comp=(0.55, 0.55, 0.58), hs=(0.78, 0.62, 0.42), lcd=(0.20, 0.35, 0.75),
             bp=(0.15, 0.30, 0.65), sw=(0.15, 0.15, 0.15), term=(0.25, 0.45, 0.85), irm=(0.15, 0.15, 0.17))
    objs = [("base", base, C["base"], "case"), ("lid", lid, C["lid"], "case lid"), ("holder", holder, C["holder"], "lid"),
            ("hs", hs, C["hs"], "inner"), ("lcd", lcd, C["lcd"], "lid show"), ("wires", wires, (0.85, 0.2, 0.2), "lid")]
    objs += [(f"cap{k}", c, C["cap"], "case lid") for k, c in enumerate(caps)]
    objs += [(f"sw{k}", s, C["sw"], "lid") for k, s in enumerate(switches)]
    for nm, s, c in comps:
        col = C["pcb"] if c == "pcb" else C["term"] if nm in TERMS else \
            C["irm"] if nm.startswith("PS101") else (0.9, 0.9, 0.9) if "провод" in nm else C["comp"]
        objs.append((nm, s, col, "inner"))
    dump_meshes(os.path.join(BUILD, "meshes.npz"), objs, tol=0.08)
    # разрезы плоскостью y = const, смотрим с -y платы (сверху для человека) на сечение
    cuts = (("lcd", L.lcd_cy), ("triac", L.tab_hole[1]))
    for tag, yc in cuts:
        half = kbox(L.xo0 - 20, L.xo1 + 20, yc, L.yo1 + 30, -5, 100)
        cut_objs = []
        for nm, s, col, grp in objs:
            if s.BoundBox.intersect(half.BoundBox):
                c = s.common(half)
                if c.Volume > 1e-3 or c.Area > 1e-3:
                    cut_objs.append((nm, c, col, grp))
        dump_meshes(os.path.join(BUILD, f"meshes_cut_{tag}.npz"), cut_objs, tol=0.08)
    json.dump(dict(variant=VARIANT, lcd=(L.lcd_cx, L.lcd_cy), btn=L.btn, z=(L.z_bb, L.z_bt, L.z_li, L.z_lo),
                   box=(L.xo0, L.xo1, L.yo0, L.yo1), cut_y=[c[1] for c in cuts], rth=rth, i_typ=i_typ, i_worst=i_worst),
              open(os.path.join(BUILD, "layout.json"), "w"), indent=1)
    print("готово:", BUILD)


try:
    main()
except SystemExit as e:
    print("ОШИБКА:", e)
except Exception:
    import traceback
    traceback.print_exc()
    raise
