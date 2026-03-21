"""
qr_pure.py — Minimal QR (Version 3-M, byte mode) using only PIL.
Supports any ASCII/ISO-8859-1 text up to 32 chars.
"""
import io
from PIL import Image, ImageDraw

# ── GF(256) ──────────────────────────────────────────────────────
GF_EXP = [0]*512
GF_LOG  = [0]*256
_v = 1
for _i in range(255):
    GF_EXP[_i] = _v
    GF_LOG[_v]  = _i
    _v = (_v << 1) ^ (0x11D if _v & 0x80 else 0)
    _v &= 0xFF
for _i in range(255, 512):
    GF_EXP[_i] = GF_EXP[_i - 255]

def _mul(a, b):
    return 0 if (a == 0 or b == 0) else GF_EXP[(GF_LOG[a] + GF_LOG[b]) % 255]

def _rs_gen(n):
    g = [1]
    for i in range(n):
        g2 = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            g2[j]   ^= c
            g2[j+1] ^= _mul(c, GF_EXP[i])
        g = g2
    return g

def _rs_ec(data, n):
    gen = _rs_gen(n)
    msg = list(data) + [0]*n
    for i in range(len(data)):
        if msg[i]:
            for j, g in enumerate(gen):
                msg[i+j] ^= _mul(g, msg[i])
    return msg[len(data):]

# ── Encode (version 3-M: 29×29, 26 data cw, 26 ec cw) ───────────
def _encode(text):
    raw = text.encode('iso-8859-1', errors='replace')[:32]
    bits = []
    def add(v, n):
        for i in range(n-1, -1, -1): bits.append((v >> i) & 1)
    add(0b0100, 4)   # byte mode
    add(len(raw), 8) # char count
    for b in raw: add(b, 8)
    add(0, 4)        # terminator
    while len(bits) % 8: bits.append(0)
    cws = [int(''.join(str(b) for b in bits[i:i+8]), 2)
           for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(cws) < 26: cws.append(pad[len(cws) % 2])
    return cws[:26]

# ── Matrix builder ───────────────────────────────────────────────
SIZE = 29

def make_qr(text):
    data = _encode(text)
    ec   = _rs_ec(data, 26)
    cws  = data + ec

    stream = []
    for cw in cws:
        for i in range(7, -1, -1): stream.append((cw >> i) & 1)

    mat  = [[0]*SIZE for _ in range(SIZE)]
    used = [[False]*SIZE for _ in range(SIZE)]

    def sm(r, c, v):
        mat[r][c] = v; used[r][c] = True

    def finder(tr, tc):
        for r in range(7):
            for c in range(7):
                v = 1 if (r in (0,6) or c in (0,6) or (2<=r<=4 and 2<=c<=4)) else 0
                if 0 <= tr+r < SIZE and 0 <= tc+c < SIZE:
                    sm(tr+r, tc+c, v)
        for i in range(8):
            if 0 <= tr+7 < SIZE and 0 <= tc+i < SIZE: sm(tr+7, tc+i, 0)
            if 0 <= tr+i < SIZE and 0 <= tc+7 < SIZE: sm(tr+i, tc+7, 0)

    finder(0, 0); finder(0, SIZE-7); finder(SIZE-7, 0)

    for i in range(8, SIZE-8):
        sm(6, i, i%2==0); sm(i, 6, i%2==0)

    sm(SIZE-8, 8, 1)  # dark module

    # alignment pattern centres for v3
    for ar, ac in [(22, 6), (6, 22), (22, 22)]:
        if not used[ar][ac]:
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    v = 1 if (abs(dr)==2 or abs(dc)==2 or (dr==0 and dc==0)) else 0
                    sm(ar+dr, ac+dc, v)

    # format info — ECC=M, mask=2
    fmt = [1,0,1,1,1,0,0,0,1,0,0,1,0,0,0]
    fp1 = [(8,0),(8,1),(8,2),(8,3),(8,4),(8,5),(8,7),(8,8),
           (7,8),(5,8),(4,8),(3,8),(2,8),(1,8),(0,8)]
    fp2 = [(SIZE-1,8),(SIZE-2,8),(SIZE-3,8),(SIZE-4,8),(SIZE-5,8),
           (SIZE-6,8),(SIZE-7,8),(8,SIZE-8),(8,SIZE-7),(8,SIZE-6),
           (8,SIZE-5),(8,SIZE-4),(8,SIZE-3),(8,SIZE-2),(8,SIZE-1)]
    for (r,c),b in zip(fp1, fmt): sm(r,c,b)
    for (r,c),b in zip(fp2, fmt): sm(r,c,b)

    # place data bits
    si = 0; col = SIZE-1; going_up = True
    while col >= 0:
        if col == 6: col -= 1
        rows = range(SIZE-1, -1, -1) if going_up else range(SIZE)
        for row in rows:
            for dc in (0, -1):
                c = col + dc
                if 0 <= c < SIZE and not used[row][c]:
                    mat[row][c] = stream[si] if si < len(stream) else 0
                    si += 1
        col -= 2; going_up = not going_up

    # mask pattern 2: (row//2 + col//3) % 2 == 0
    for r in range(SIZE):
        for c in range(SIZE):
            if not used[r][c]:
                if (r//2 + c//3) % 2 == 0:
                    mat[r][c] ^= 1

    return mat


def qr_to_png_bytes(text, module_px=8, quiet=3):
    mat = make_qr(text)
    n   = len(mat)
    sz  = (n + 2*quiet) * module_px
    img = Image.new('1', (sz, sz), 1)
    draw= ImageDraw.Draw(img)
    for r, row in enumerate(mat):
        for c, v in enumerate(row):
            if v:
                x0 = (c+quiet)*module_px; y0 = (r+quiet)*module_px
                draw.rectangle([x0, y0, x0+module_px-1, y0+module_px-1], fill=0)
    buf = io.BytesIO(); img.save(buf, 'PNG'); return buf.getvalue()
