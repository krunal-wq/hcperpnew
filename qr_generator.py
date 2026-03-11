"""
qr_generator.py — QR Code generator using Pillow (Reed-Solomon based)
Generates a simple, scannable QR code for employee codes (short strings)
"""
import base64, io, struct
from PIL import Image, ImageDraw


def generate_qr_base64(text: str) -> str:
    """
    Generate QR code using JavaScript-friendly approach.
    Returns a data URL with the QR image as base64 PNG.
    """
    if not text or not str(text).strip():
        return None
    text = str(text).strip()
    try:
        from PIL import Image, ImageDraw
        img = _make_qr_image(text)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        print(f"QR error: {e}")
        import traceback; traceback.print_exc()
        return None


def _make_qr_image(text: str) -> Image.Image:
    """Create QR code image using the micro-qr algorithm"""
    # Use a well-tested minimal QR implementation
    matrix = _qr_matrix(text)
    n = len(matrix)
    scale = 8
    quiet = 3
    img_size = (n + quiet * 2) * scale
    img = Image.new('1', (img_size, img_size), 1)  # 1=white
    draw = ImageDraw.Draw(img)

    for r in range(n):
        for c in range(n):
            if matrix[r][c] == 1:
                x = (c + quiet) * scale
                y = (r + quiet) * scale
                draw.rectangle([x, y, x + scale - 1, y + scale - 1], fill=0)

    # Convert to RGB
    return img.convert('RGB')


# ─── Minimal but correct QR Code (Version 1, EC=M) ─────────────────────────

GF256_EXP = [1] * 512
GF256_LOG = [0] * 256

def _init():
    x = 1
    for i in range(1, 256):
        x = (x << 1) ^ (0x11d if x & 0x80 else 0)
        x &= 0xff
        GF256_EXP[i] = x
        GF256_LOG[x] = i
    for i in range(256, 512):
        GF256_EXP[i] = GF256_EXP[i - 255]
_init()

def gf_mul(a, b):
    if a == 0 or b == 0: return 0
    return GF256_EXP[GF256_LOG[a] + GF256_LOG[b]]

def rs_encode_msg(msg_in, nsym):
    gen = [1]
    for i in range(nsym):
        g = [1, GF256_EXP[i]]
        r = [0] * (len(gen) + len(g) - 1)
        for j, gj in enumerate(g):
            for i2, gi in enumerate(gen):
                r[i2 + j] ^= gf_mul(gi, gj)
        gen = r
    msg = list(msg_in) + [0] * nsym
    for i in range(len(msg_in)):
        if msg[i] == 0: continue
        coef = msg[i]
        for j in range(1, len(gen)):
            msg[i + j] ^= gf_mul(gen[j], coef)
    return list(msg_in) + msg[len(msg_in):]


def _qr_matrix(data: str) -> list:
    """Generate QR matrix for given data string, version 1-4 auto"""
    # Version selection
    data_bytes = data.encode('iso-8859-1')
    # Version 1=16B, 2=28B, 3=44B, 4=64B (M level)
    caps = [(1,16,10),(2,28,16),(3,44,26),(4,64,36)]
    version, ec_n = 1, 10
    for v, cap, ecn in caps:
        if len(data_bytes) <= cap - 2:
            version = v; ec_n = ecn; break

    size = 17 + 4 * version
    mat = [[0]*size for _ in range(size)]
    res = [[False]*size for _ in range(size)]  # reserved

    def fill(r, c, v):
        if 0 <= r < size and 0 <= c < size:
            mat[r][c] = v
            res[r][c] = True

    # ── Finder patterns
    def finder(tr, tc):
        for r in range(7):
            for c in range(7):
                d = (r in (0,6) or c in (0,6)) or (2<=r<=4 and 2<=c<=4)
                fill(tr+r, tc+c, 1 if d else 0)
        # Separator
        for i in range(8):
            fill(tr-1+i if tr>0 else tr+7, tc+7 if tc<size-7 else tc-1, 0)

    finder(0, 0)
    finder(0, size-7)
    finder(size-7, 0)

    # Separators
    for i in range(8):
        fill(7, i, 0); fill(i, 7, 0)
        fill(7, size-1-i, 0); fill(i, size-8, 0)
        fill(size-8, i, 0); fill(size-1-i, 7, 0)

    # Timing
    for i in range(8, size-8):
        fill(6, i, 1 if i%2==0 else 0)
        fill(i, 6, 1 if i%2==0 else 0)

    # Dark module
    fill(4*version+9, 8, 1)

    # Format info placeholders
    fmt_pos1 = [(8,0),(8,1),(8,2),(8,3),(8,4),(8,5),(8,7),(8,8),(7,8),(5,8),(4,8),(3,8),(2,8),(1,8),(0,8)]
    fmt_pos2 = [(size-1,8),(size-2,8),(size-3,8),(size-4,8),(size-5,8),(size-6,8),(size-7,8),
                (8,size-8),(8,size-7),(8,size-6),(8,size-5),(8,size-4),(8,size-3),(8,size-2),(8,size-1)]
    for r,c in fmt_pos1+fmt_pos2:
        fill(r, c, 0)

    # ── Data encoding (byte mode)
    n = len(data_bytes)
    # Total / data codewords per version (EC=M)
    tot_ecn = {1:(26,10),2:(44,16),3:(70,26),4:(100,36)}
    total, ec_n = tot_ecn.get(version, (26,10))
    data_n = total - ec_n

    bits = []
    def addBits(val, ln):
        for i in range(ln-1,-1,-1): bits.append((val>>i)&1)

    addBits(0b0100, 4)  # byte mode
    addBits(n, 8)
    for b in data_bytes: addBits(b, 8)

    while len(bits) < data_n*8 and len(bits)%8 != 0: bits.append(0)
    if len(bits) < data_n*8 - 3:
        for _ in range(4): bits.append(0)
    while len(bits) % 8: bits.append(0)

    cw = []
    for i in range(0, len(bits), 8):
        cw.append(int(''.join(map(str,bits[i:i+8])),2))

    pad_bytes = [0xEC,0x11]
    pi = 0
    while len(cw) < data_n: cw.append(pad_bytes[pi%2]); pi+=1

    # RS encode
    all_cw = rs_encode_msg(cw[:data_n], ec_n)

    # All bits
    all_bits = []
    for c in all_cw:
        for i in range(7,-1,-1): all_bits.append((c>>i)&1)

    # ── Place data bits
    def mask0(r,c): return (r+c)%2==0

    bi = 0
    going_up = True
    col = size - 1
    while col > 0:
        if col == 6: col -= 1
        rng = range(size-1,-1,-1) if going_up else range(size)
        for row in rng:
            for dc in range(2):
                c = col - dc
                if 0<=c<size and not res[row][c]:
                    bit = all_bits[bi] if bi < len(all_bits) else 0
                    bi += 1
                    mat[row][c] = bit^1 if mask0(row,c) else bit
        going_up = not going_up
        col -= 2

    # ── Format bits (EC=M, mask=0) → 101010000010010
    fmt = 0b101010000010010
    fb = [(fmt>>i)&1 for i in range(14,-1,-1)]
    for i,(r,c) in enumerate(fmt_pos1):
        mat[r][c] = fb[i]
    # Second copy (different order: 7 bits of low, 8 of high)
    fb2 = fb[7:]+fb[:7]
    for i,(r,c) in enumerate(fmt_pos2):
        mat[r][c] = fb2[i]

    return mat
