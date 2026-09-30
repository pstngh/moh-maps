"""quake_texdef must reproduce Source texture vectors through Q3's old-style projection."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mohkit import geom  # noqa: E402
from mohkit.source.convert import quake_texdef, texture_axis  # noqa: E402


def q3_st(p, normal, shift, rotate, scale):
    """Quake 3 QuakeTextureVecs forward mapping (texel units)."""
    xv, yv = texture_axis(normal)
    vecs = [list(xv), list(yv)]
    ang = math.radians(rotate)
    sinv, cosv = math.sin(ang), math.cos(ang)
    sv = next(i for i in range(3) if vecs[0][i])
    tv = next(i for i in range(3) if vecs[1][i])
    for i in range(2):
        ns = cosv * vecs[i][sv] - sinv * vecs[i][tv]
        nt = sinv * vecs[i][sv] + cosv * vecs[i][tv]
        vecs[i][sv], vecs[i][tv] = ns, nt
    return (sum(vecs[0][j] * p[j] for j in range(3)) / scale[0] + shift[0],
            sum(vecs[1][j] * p[j] for j in range(3)) / scale[1] + shift[1])


def test_random_planes():
    rnd = random.Random(1)
    worst = 0.0
    for _ in range(2000):
        n = geom.normalize((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        d = rnd.uniform(-500, 500)
        # Source-style: texture axes built from the plane's projection axes, rotated and scaled
        xv, yv = texture_axis(n)
        rot = math.radians(rnd.uniform(0, 360))
        s1, s2 = rnd.choice([0.25, 0.5, 1, 2]), rnd.choice([0.25, 0.5, 1, 2])
        if rnd.random() < 0.3:
            s1 = -s1  # mirrored
        c, s = math.cos(rot), math.sin(rot)
        svec = tuple((c * xv[i] + s * yv[i]) / s1 for i in range(3)) + (rnd.uniform(-300, 300),)
        tvec = tuple((-s * xv[i] + c * yv[i]) / s2 for i in range(3)) + (rnd.uniform(-300, 300),)
        shift, rotate, scale = quake_texdef(n, d, svec, tvec)
        u = geom.normalize(geom.cross(n, (0.3, 0.7, 0.1)))
        v = geom.cross(n, u)
        for _ in range(5):
            a, b = rnd.uniform(-1000, 1000), rnd.uniform(-1000, 1000)
            p = tuple(n[i] * d + u[i] * a + v[i] * b for i in range(3))
            want = (sum(svec[i] * p[i] for i in range(3)) + svec[3], sum(tvec[i] * p[i] for i in range(3)) + tvec[3])
            got = q3_st(p, n, shift, rotate, scale)
            worst = max(worst, abs(want[0] - got[0]), abs(want[1] - got[1]))
    assert worst < 1e-6, worst


if __name__ == "__main__":
    test_random_planes()
    print("ok")
