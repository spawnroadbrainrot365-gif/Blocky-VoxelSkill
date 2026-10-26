#!/usr/bin/env python3
"""REFERENCE SCRIPT for the blocky dragon style.
Builds a pair of wings from boxes, pyramids and a stair-step voxel membrane,
writes OBJ + MTL and renders a 2-view preview. Needs numpy + Pillow.
Output folder: $OUT_DIR (default: current folder)."""
import math, os
import numpy as np
from PIL import Image

OUT = os.environ.get("OUT_DIR", ".")
os.makedirs(OUT, exist_ok=True)
NAME = "dragon_wings"
SC = 0.25  # design units -> OBJ units

COL = {  # 0-255, sampled from the user's screenshots (fully lit faces)
    "Orange":   (204, 94, 10),
    "Membrane": (86, 86, 90),
    "Claw":     (24, 11, 2),
}

# ------------------------------------------------------------------ vectors
def add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def mul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def unit(a):
    l = math.sqrt(dot(a, a)); return (a[0]/l, a[1]/l, a[2]/l)
def centroid(f):
    n = len(f)
    return (sum(p[0] for p in f)/n, sum(p[1] for p in f)/n, sum(p[2] for p in f)/n)
def face_normal(f):  # Newell
    nx = ny = nz = 0.0
    n = len(f)
    for i in range(n):
        x1, y1, z1 = f[i]; x2, y2, z2 = f[(i+1) % n]
        nx += (y1-y2)*(z1+z2); ny += (z1-z2)*(x1+x2); nz += (x1-x2)*(y1+y2)
    return unit((nx, ny, nz))
def orient(f, inside):
    if dot(face_normal(f), sub(centroid(f), inside)) < 0:
        return f[::-1]
    return f

# ------------------------------------------------------------------ primitives
def make_box(center, ang_deg, length, width, thick):
    """Box in the wing plane (XY); long axis at ang_deg, thickness along Z."""
    th = math.radians(ang_deg)
    a = (math.cos(th), math.sin(th), 0.0)
    b = (-math.sin(th), math.cos(th), 0.0)
    n = (0.0, 0.0, 1.0)
    ha, hb, hn = length/2, width/2, thick/2
    def c(sa, sb, sn):
        return add(center, add(mul(a, sa*ha), add(mul(b, sb*hb), mul(n, sn*hn))))
    faces = [
        [c(+1,-1,-1), c(+1,+1,-1), c(+1,+1,+1), c(+1,-1,+1)],
        [c(-1,-1,-1), c(-1,-1,+1), c(-1,+1,+1), c(-1,+1,-1)],
        [c(-1,+1,-1), c(-1,+1,+1), c(+1,+1,+1), c(+1,+1,-1)],
        [c(-1,-1,-1), c(+1,-1,-1), c(+1,-1,+1), c(-1,-1,+1)],
        [c(-1,-1,+1), c(+1,-1,+1), c(+1,+1,+1), c(-1,+1,+1)],
        [c(-1,-1,-1), c(-1,+1,-1), c(+1,+1,-1), c(+1,-1,-1)],
    ]
    for f in faces:
        assert dot(face_normal(f), sub(centroid(f), center)) > 0, "inward box face"
    return faces

def make_pyramid(tip_base, ang_deg, width, thick, height, embed):
    """Dark claw: rectangular base (embedded in the bone) tapering to a point."""
    th = math.radians(ang_deg)
    a = (math.cos(th), math.sin(th), 0.0)
    b = (-math.sin(th), math.cos(th), 0.0)
    n = (0.0, 0.0, 1.0)
    bc = sub(tip_base, mul(a, embed))
    apex = add(tip_base, mul(a, height))
    def c(sb, sn):
        return add(bc, add(mul(b, sb*width/2), mul(n, sn*thick/2)))
    inside = add(bc, mul(a, (height+embed)*0.25))
    quad = [c(-1,-1), c(-1,+1), c(+1,+1), c(+1,-1)]
    tris = [[c(-1,-1), c(-1,+1), apex], [c(-1,+1), c(+1,+1), apex],
            [c(+1,+1), c(+1,-1), apex], [c(+1,-1), c(-1,-1), apex]]
    return [orient(quad, inside)] + [orient(t, inside) for t in tris]

def bone(p0, p1, segs):
    """Stepped bone: each segment is a box with two stacked ridges (ziggurat cross-section)."""
    dx, dy = p1[0]-p0[0], p1[1]-p0[1]
    L = math.hypot(dx, dy); ang = math.degrees(math.atan2(dy, dx))
    ux, uy = dx/L, dy/L
    at = lambda s: (p0[0]+ux*s, p0[1]+uy*s, 0.0)
    out = []
    for k, (f0, f1, w, t) in enumerate(segs):
        s0 = f0*L - (0.3 if k else 0.0)   # tuck into the previous (wider) segment
        s1 = f1*L
        out += make_box(at((s0+s1)/2), ang, s1-s0, w, t)
        for wf, dt, a0, a1 in ((0.66, 0.20, 0.45, 0.30), (0.34, 0.40, 0.90, 0.60)):
            r0, r1 = s0+a0, s1-a1
            if r1 - r0 > 0.8:
                out += make_box(at((r0+r1)/2), ang, r1-r0, w*wf, t+dt)
    return out

# ------------------------------------------------------------------ membrane (voxel sheet)
def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]; x2, y2 = poly[(k+1) % n]
        if (y1 > y) != (y2 > y):
            if x1 + (y-y1)*(x2-x1)/(y2-y1) > x:
                inside = not inside
    return inside

def scallop(a, b, pivot, k, n=14):
    mid = ((a[0]+b[0])/2, (a[1]+b[1])/2)
    c = (mid[0]+(pivot[0]-mid[0])*k, mid[1]+(pivot[1]-mid[1])*k)
    pts = []
    for i in range(n+1):
        t = i/n
        pts.append(((1-t)**2*a[0] + 2*(1-t)*t*c[0] + t*t*b[0],
                    (1-t)**2*a[1] + 2*(1-t)*t*c[1] + t*t*b[1]))
    return pts

def build_membrane(poly, g, hz):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    i0 = math.floor(min(xs)/g); i1 = math.ceil(max(xs)/g)
    j0 = math.floor(min(ys)/g); j1 = math.ceil(max(ys)/g)
    NW, NH = i1-i0, j1-j0
    m = [[point_in_poly((i0+i+.5)*g, (j0+j+.5)*g, poly) for i in range(NW)] for j in range(NH)]
    F = lambda i, j: 0 <= i < NW and 0 <= j < NH and m[j][i]
    changed = True
    while changed:                       # drop single-cell crumbs
        changed = False
        for j in range(NH):
            for i in range(NW):
                if m[j][i] and (F(i-1,j)+F(i+1,j)+F(i,j-1)+F(i,j+1)) <= 1:
                    m[j][i] = False; changed = True
    X = lambda i: (i0+i)*g
    Y = lambda j: (j0+j)*g
    faces = []
    # front/back sheets, greedy-merged rectangles
    open_r, rects = {}, []
    for j in range(NH+1):
        runs = set()
        if j < NH:
            i = 0
            while i < NW:
                if m[j][i]:
                    s = i
                    while i < NW and m[j][i]: i += 1
                    runs.add((s, i))
                else:
                    i += 1
        for key in list(open_r):
            if key not in runs:
                rects.append((key[0], key[1], open_r.pop(key), j))
        for key in runs:
            if key not in open_r:
                open_r[key] = j
    for ia, ib, ja, jb in rects:
        x0, x1, y0, y1 = X(ia), X(ib), Y(ja), Y(jb)
        faces.append([(x0,y0,hz), (x1,y0,hz), (x1,y1,hz), (x0,y1,hz)])
        faces.append([(x0,y0,-hz), (x0,y1,-hz), (x1,y1,-hz), (x1,y0,-hz)])
    # stair-step edges
    for j in range(NH):
        for dj in (+1, -1):
            i = 0
            while i < NW:
                if F(i,j) and not F(i,j+dj):
                    s = i
                    while i < NW and F(i,j) and not F(i,j+dj): i += 1
                    xa, xb = X(s), X(i)
                    if dj > 0:
                        y = Y(j+1); faces.append([(xa,y,-hz), (xa,y,hz), (xb,y,hz), (xb,y,-hz)])
                    else:
                        y = Y(j);   faces.append([(xa,y,-hz), (xb,y,-hz), (xb,y,hz), (xa,y,hz)])
                else:
                    i += 1
    for i in range(NW):
        for di in (+1, -1):
            j = 0
            while j < NH:
                if F(i,j) and not F(i+di,j):
                    s = j
                    while j < NH and F(i,j) and not F(i+di,j): j += 1
                    ya, yb = Y(s), Y(j)
                    if di > 0:
                        x = X(i+1); faces.append([(x,ya,-hz), (x,yb,-hz), (x,yb,hz), (x,ya,hz)])
                    else:
                        x = X(i);   faces.append([(x,ya,-hz), (x,ya,hz), (x,yb,hz), (x,yb,-hz)])
                else:
                    j += 1
    return faces

# ------------------------------------------------------------------ the wing (right side, +X)
def build_wing():
    bones, claws = [], []
    S = (1.6, 0.0)          # shoulder
    W = (4.0, 7.4)          # wrist (finger pivot)
    H = (1.7, -3.0)         # lower inner corner of the membrane
    fingers = [(34, 14.0), (9, 16.5), (-16, 15.5), (-42, 12.5)]   # (angle deg, length)

    bones += make_box((S[0], S[1], 0), 0, 3.0, 3.0, 2.8)
    bones += make_box((W[0], W[1], 0), 0, 3.0, 3.0, 2.6)
    bones += bone(S, W, [(0, .55, 2.4, 2.0), (.55, 1.0, 2.0, 1.7)])

    unit_d = []
    for ang, L in fingers:
        r = math.radians(ang)
        d = (math.cos(r), math.sin(r)); unit_d.append(d)
        p1 = (W[0]+d[0]*L, W[1]+d[1]*L)
        bones += bone(W, p1, [(0, .38, 2.1, 1.8), (.38, .70, 1.7, 1.5), (.70, 1.0, 1.25, 1.2)])
        claws += make_pyramid((p1[0], p1[1], 0), ang, 1.0, 0.9, 2.8, 0.5)
    claws += make_pyramid((W[0]+0.2, W[1]+1.4, 0), 78, 1.8, 1.6, 4.0, 0.5)   # thumb claw

    # membrane outline: along arm, under first finger, scalloped between fingertips, back to the shoulder
    T = [(W[0]+unit_d[i][0]*(fingers[i][1]-1.0), W[1]+unit_d[i][1]*(fingers[i][1]-1.0)) for i in range(4)]
    r1 = math.radians(fingers[0][0])
    off = (math.sin(r1)*0.6, -math.cos(r1)*0.6)
    T1 = (T[0][0]+off[0], T[0][1]+off[1])
    poly = [S, W, (W[0]+off[0], W[1]+off[1]), T1]
    chain = [T1, T[1], T[2], T[3], H]
    for a_, b_ in zip(chain[:-1], chain[1:]):
        poly += scallop(a_, b_, W, 0.34)[1:-1]
        poly.append(b_)
    memb = build_membrane(poly, 1.0, 0.25)
    return {"Bones": bones, "Membrane": memb, "Claws": claws}

def mirror(faces):
    return [[(-x, y, z) for (x, y, z) in reversed(f)] for f in faces]

# ------------------------------------------------------------------ writers
def write_obj(path, objects):
    lines = ["# Blocky dragon wings (pair)", "# +X = right wing, -X = left wing, +Y = up, wing plane = XY",
             f"mtllib {NAME}.mtl"]
    vo = no = 0
    for name, mat, faces in objects:
        vmap, vl, nmap, nl, fl = {}, [], {}, [], []
        for f in faces:
            nk = tuple(round(c, 4) for c in face_normal(f))
            if nk not in nmap:
                nl.append(nk); nmap[nk] = len(nl) + no
            ni = nmap[nk]
            idx = []
            for p in f:
                pk = tuple(round(c*SC, 4) for c in p)
                if pk not in vmap:
                    vl.append(pk); vmap[pk] = len(vl) + vo
                idx.append(vmap[pk])
            fl.append("f " + " ".join(f"{i}//{ni}" for i in idx))
        lines.append(f"o {name}")
        lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in vl]
        lines += [f"vn {x:.4f} {y:.4f} {z:.4f}" for x, y, z in nl]
        lines += [f"usemtl {mat}", "s off"] + fl
        vo += len(vl); no += len(nl)
    open(path, "w").write("\n".join(lines) + "\n")

def write_mtl(path):
    out = ["# materials"]
    for name, (r, g, b) in COL.items():
        kd = (r/255, g/255, b/255)
        out += [f"newmtl {name}",
                "Ka %.3f %.3f %.3f" % tuple(c*0.35 for c in kd),
                "Kd %.3f %.3f %.3f" % kd,
                "Ks 0.000 0.000 0.000", "Ns 8", "d 1.0", "illum 1", ""]
    open(path, "w").write("\n".join(out))

def read_obj(path):
    V, objs, cur = [], [], None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] == "v": V.append(tuple(map(float, t[1:4])))
        elif t[0] == "o": cur = {"name": t[1], "mat": None, "faces": []}; objs.append(cur)
        elif t[0] == "usemtl": cur["mat"] = t[1]
        elif t[0] == "f": cur["faces"].append([V[int(x.split("/")[0])-1] for x in t[1:]])
    return objs

# ------------------------------------------------------------------ preview renderer (z-buffer)
def raster_tri(img, zb, sx, sy, sz, col):
    Hh, Ww = zb.shape
    x0, x1, x2 = sx; y0, y1, y2 = sy; z0, z1, z2 = sz
    minx = max(int(math.floor(min(sx))), 0); maxx = min(int(math.ceil(max(sx))), Ww-1)
    miny = max(int(math.floor(min(sy))), 0); maxy = min(int(math.ceil(max(sy))), Hh-1)
    if minx > maxx or miny > maxy: return
    den = (y1-y2)*(x0-x2) + (x2-x1)*(y0-y2)
    if abs(den) < 1e-9: return
    X, Y = np.meshgrid(np.arange(minx, maxx+1, dtype=np.float32)+.5,
                       np.arange(miny, maxy+1, dtype=np.float32)+.5)
    w0 = ((y1-y2)*(X-x2) + (x2-x1)*(Y-y2))/den
    w1 = ((y2-y0)*(X-x2) + (x0-x2)*(Y-y2))/den
    w2 = 1.0 - w0 - w1
    m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
    if not m.any(): return
    Z = w0*z0 + w1*z1 + w2*z2
    zs = zb[miny:maxy+1, minx:maxx+1]
    upd = m & (Z > zs)
    if not upd.any(): return
    zs[upd] = Z[upd]
    img[miny:maxy+1, minx:maxx+1][upd] = col

def render(objs, yaw, pitch, S=600, ss=2, bg=(36, 36, 38)):
    yw, pt = math.radians(yaw), math.radians(pitch)
    Ry = np.array([[math.cos(yw), 0, math.sin(yw)], [0, 1, 0], [-math.sin(yw), 0, math.cos(yw)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(pt), -math.sin(pt)], [0, math.sin(pt), math.cos(pt)]])
    R = Rx @ Ry
    allv = np.array([v for o in objs for f in o["faces"] for v in f])
    ctr = (allv.max(0) + allv.min(0))/2
    rv = (allv-ctr) @ R.T
    ext = max(np.ptp(rv[:, 0]), np.ptp(rv[:, 1]))
    sc = S*ss*0.90/ext
    N = S*ss
    img = np.zeros((N, N, 3), np.float32); img[:] = bg
    zb = np.full((N, N), -1e9, np.float32)
    L1 = np.array([-0.4, 0.6, 0.7]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.7, -0.1, 0.3]); L2 /= np.linalg.norm(L2)
    for o in objs:
        base = np.array(COL[o["mat"]], np.float32)
        for f in o["faces"]:
            P = (np.array(f)-ctr) @ R.T
            n = np.cross(P[1]-P[0], P[2]-P[0]); nn = np.linalg.norm(n)
            if nn < 1e-12: continue
            n /= nn
            if n[2] <= 1e-4: continue           # back-face
            k = 0.42 + 0.62*max(0, n@L1) + 0.14*max(0, n@L2)
            col = np.clip(base*k, 0, 255)
            sx = N/2 + P[:, 0]*sc; sy = N/2 - P[:, 1]*sc; sz = P[:, 2]
            for t in range(1, len(P)-1):
                raster_tri(img, zb, (sx[0], sx[t], sx[t+1]), (sy[0], sy[t], sy[t+1]),
                           (sz[0], sz[t], sz[t+1]), col)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return im.resize((S, S), Image.LANCZOS)

# ------------------------------------------------------------------ main
if __name__ == "__main__":
    wing = build_wing()
    objects = []
    for side, tf in (("R", lambda f: f), ("L", mirror)):
        for part, mat in (("Bones", "Orange"), ("Membrane", "Membrane"), ("Claws", "Claw")):
            objects.append((f"Wing_{side}_{part}", mat, tf(wing[part])))
    obj_path = f"{OUT}/{NAME}.obj"
    write_obj(obj_path, objects)
    write_mtl(f"{OUT}/{NAME}.mtl")

    parsed = read_obj(obj_path)
    allv = np.array([v for o in parsed for f in o["faces"] for v in f])
    print("objects:", [(o["name"], len(o["faces"])) for o in parsed])
    print("faces:", sum(len(o["faces"]) for o in parsed), " bbox min", allv.min(0).round(2), "max", allv.max(0).round(2))
    assert np.isfinite(allv).all()

    a = render(parsed, 22, 14)
    b = render(parsed, -38, 20)
    sheet = Image.new("RGB", (a.width*2, a.height), (36, 36, 38))
    sheet.paste(a, (0, 0)); sheet.paste(b, (a.width, 0))
    sheet.save(f"{OUT}/{NAME}_preview.png")
    print("done")
