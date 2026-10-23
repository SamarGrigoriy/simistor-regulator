
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
