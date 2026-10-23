#!/usr/bin/env python3
"""
Картинки корпуса из сеток, которые выгружает case.py (build*/meshes*.npz).

    python3 enclosure/render.py              # build/*.png (основной, 3 А)
    python3 enclosure/render.py build_4A     # запасной вариант 4 А

Свой растеризатор: z-буфер на C (собирается gcc при первом запуске в build/),
плоская заливка, контуры по скачкам глубины и нормалей, сглаживание 2x.
FreeCAD без экрана картинку не отрисовывает, поэтому так.
"""
import ctypes
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "build")

C_SRC = r"""
#include <math.h>
void raster(int W, int H, int n, const float *t, int *tid, float *zb) {
    for (int i = 0; i < n; i++) {
        const float *p = t + 9 * i;
        float x0 = p[0], y0 = p[1], z0 = p[2], x1 = p[3], y1 = p[4], z1 = p[5], x2 = p[6], y2 = p[7], z2 = p[8];
        float area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
        if (fabsf(area) < 1e-9f) continue;
        int xa = (int)floorf(fminf(x0, fminf(x1, x2))), xb = (int)ceilf(fmaxf(x0, fmaxf(x1, x2)));
        int ya = (int)floorf(fminf(y0, fminf(y1, y2))), yb = (int)ceilf(fmaxf(y0, fmaxf(y1, y2)));
        if (xa < 0) xa = 0; if (ya < 0) ya = 0; if (xb > W - 1) xb = W - 1; if (yb > H - 1) yb = H - 1;
        for (int y = ya; y <= yb; y++) {
            float py = y + 0.5f;
            for (int x = xa; x <= xb; x++) {
                float px = x + 0.5f;
                float w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area;
                float w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area;
                float w2 = 1.0f - w0 - w1;
                if (w0 < -1e-5f || w1 < -1e-5f || w2 < -1e-5f) continue;
                float z = w0 * z0 + w1 * z1 + w2 * z2;
                int k = y * W + x;
                if (z < zb[k]) { zb[k] = z; tid[k] = i; }
            }
        }
    }
}
"""


def load_lib():
    so = os.path.join(BUILD, "_raster.so")
    src = os.path.join(BUILD, "_raster.c")
    stale = not os.path.exists(so) or not os.path.exists(src) or open(src).read() != C_SRC
    if stale:
        open(src, "w").write(C_SRC)
        subprocess.check_call(["gcc", "-O2", "-shared", "-fPIC", "-o", so, src, "-lm"])
    lib = ctypes.CDLL(so)
    f = lib.raster
    f.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    return f


RASTER = None


def load(name):
    d = np.load(os.path.join(BUILD, name))
    objs = []
    for i, nm in enumerate(d["names"]):
        v = d["V"][d["voff"][i]:d["voff"][i + 1]]
        t = d["T"][d["toff"][i]:d["toff"][i + 1]]
        objs.append(dict(name=str(nm), group=str(d["groups"][i]).split(), color=d["colors"][i], V=v, T=t))
    return objs


def norm(v):
    return v / np.linalg.norm(v)


def render(objs, eye, up, out, size=(1400, 1050), ss=2, offsets=None, margin=0.06, light=None):
    """eye — направление от сцены к камере, up — вверх на картинке; ортогональная проекция."""
    global RASTER
    if RASTER is None:
        RASTER = load_lib()
    W, H = size[0] * ss, size[1] * ss
    e = norm(np.array(eye, float))
    u = np.array(up, float)
    u = norm(u - e * np.dot(u, e))
    r = np.cross(u, e)
    tris, cols, oids = [], [], []
    for k, o in enumerate(objs):
        v = o["V"].astype(np.float64)
        if offsets and o["name"] in offsets:
            v = v + np.array(offsets[o["name"]])
        elif offsets:
            for g in o["group"]:
                if g in offsets:
                    v = v + np.array(offsets[g])
                    break
        tris.append(v[o["T"]])
        cols.append(np.repeat(o["color"][None, :], len(o["T"]), 0))
        oids.append(np.full(len(o["T"]), k))
    P = np.concatenate(tris)            # n x 3 x 3
    C = np.concatenate(cols)
    O = np.concatenate(oids)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    P, C, O, n = P[ok], C[ok], O[ok], n[ok] / ln[ok, None]
    n[np.einsum("ij,j->i", n, e) < 0] *= -1        # двусторонняя заливка
    sx = P @ r
    sy = P @ u
    sz = -(P @ e)
    x0, x1, y0, y1 = sx.min(), sx.max(), sy.min(), sy.max()
    sc = min(W * (1 - 2 * margin) / (x1 - x0), H * (1 - 2 * margin) / (y1 - y0))
    X = (sx - (x0 + x1) / 2) * sc + W / 2
    Y = H / 2 - (sy - (y0 + y1) / 2) * sc
    T = np.ascontiguousarray(np.stack([X, Y, sz], axis=2).reshape(-1, 9), dtype=np.float32)
    tid = np.full(W * H, -1, dtype=np.int32)
    zb = np.full(W * H, np.inf, dtype=np.float32)
    RASTER(W, H, len(T), T.ctypes.data, tid.ctypes.data, zb.ctypes.data)
    tid = tid.reshape(H, W)
    zb = zb.reshape(H, W)
    L1 = norm(e + 0.6 * u + 0.4 * r) if light is None else norm(np.array(light, float))
    L2 = norm(e - 0.7 * r - 0.3 * u)
    sh = 0.32 + 0.55 * np.clip(n @ L1, 0, 1) + 0.22 * np.clip(n @ L2, 0, 1)
    tc = np.clip(C * sh[:, None], 0, 1)
    img = np.ones((H, W, 3))
    m = tid >= 0
    img[m] = tc[tid[m]]
    # контуры: другой объект, скачок глубины, излом нормали
    oid = np.where(m, O[np.clip(tid, 0, None)], -1)
    nn = np.where(m[..., None], n[np.clip(tid, 0, None)], 0)
    edge = np.zeros((H, W), bool)
    depth_tol = 0.3  # мм: видна гравировка 0,5 мм
    for dy, dx in ((0, 1), (1, 0)):
        a = (slice(0, H - dy), slice(0, W - dx))
        b = (slice(dy, H), slice(dx, W))
        diff_o = oid[a] != oid[b]
        za, zb2 = zb[a], zb[b]
        diff_z = np.abs(np.where(np.isfinite(za) & np.isfinite(zb2), za - zb2, 0)) > depth_tol
        diff_n = np.einsum("ijk,ijk->ij", nn[a], nn[b]) < 0.80
        ed = (diff_o | diff_z | diff_n) & (m[a] | m[b])
        edge[a] |= ed
    img[edge] *= 0.25
    im = Image.fromarray((img * 255).astype(np.uint8)).resize(size, Image.LANCZOS)
    im.save(out)
    print("  ", os.path.basename(out))


def main():
    allobj = load("meshes.npz")
    # Лицо корпуса — +Z, «верх» для человека — -y платы (= +Y), «вправо» — +X.
    F, UP, RT = np.array([0, 0, 1.0]), np.array([0, 1.0, 0]), np.array([1.0, 0, 0])
    closed = [o for o in allobj if "case" in o["group"] or "show" in o["group"]]
    render(closed, F * 1.0 + RT * 0.55 - UP * 0.45, UP, os.path.join(BUILD, "view_closed.png"))
    render(closed, F * 1.0 - RT * 0.45 + UP * 0.55, UP, os.path.join(BUILD, "view_closed_above.png"))
    render(closed, F, UP, os.path.join(BUILD, "view_front.png"), margin=0.04)
    # снизу (клеммники) и слева (радиатор, вентиляция)
    render(closed, -UP + F * 0.25, F, os.path.join(BUILD, "view_bottom_wall.png"), size=(1400, 800))
    render(closed, -RT + F * 0.25 - UP * 0.1, F, os.path.join(BUILD, "view_left_wall.png"), size=(1400, 800))
    # открытый: крышка с ЖКИ и кнопками поднята
    lift = 60.0
    render(allobj, F * 1.0 + RT * 0.65 - UP * 0.75, UP, os.path.join(BUILD, "view_open.png"),
           offsets={o["name"]: (0, 0, lift) for o in allobj if "lid" in o["group"]}, size=(1400, 1250))
    inner = [o for o in allobj if "lid" not in o["group"]]
    render(inner, F, UP, os.path.join(BUILD, "view_inside_top.png"), margin=0.04)
    render(inner, F * 1.0 + RT * 0.5 - UP * 0.6, UP, os.path.join(BUILD, "view_inside_iso.png"), size=(1400, 1100))
    # взрыв-схема: снизу вверх — основание, плата с радиатором, держатель с кнопками и ЖКИ,
    # толкатели, крышка (порядок сборки обратный)
    lifts = {"base": 0.0, "holder": 105.0, "lcd": 105.0, "wires": 105.0, "lid": 165.0}
    exploded = {}
    for o in allobj:
        nm = o["name"]
        if nm in lifts:
            dz = lifts[nm]
        elif nm.startswith("sw"):
            dz = 105.0
        elif nm.startswith("cap"):
            dz = 140.0
        else:
            dz = 50.0                      # плата, детали, радиатор
        exploded[nm] = (0, 0, dz)
    render(allobj, F * 0.75 + RT * 0.65 - UP * 1.0, F, os.path.join(BUILD, "view_exploded.png"),
           offsets=exploded, size=(1300, 1700), margin=0.03)
    lidside = [o for o in allobj if "lid" in o["group"]]
    render(lidside, -F, UP, os.path.join(BUILD, "view_lid_inside.png"), margin=0.04)
    # разрезы y = const: смотрим сверху для человека (с -y платы) на сечение
    for tag in ("lcd", "triac"):
        cut = load(f"meshes_cut_{tag}.npz")
        render(cut, UP * 1.0 + F * 0.0001, F, os.path.join(BUILD, f"view_section_{tag}.png"), size=(1400, 900),
               light=(UP * 1.0 + F * 0.5 + RT * 0.3))


if __name__ == "__main__":
    main()
