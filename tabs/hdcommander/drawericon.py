"""Build a minimal Workbench drawer icon (.info) so folders we create show up in Workbench."""
import struct

_W, _H, _DEPTH = 48, 24, 2
# 4-colour Workbench palette: 0 grey, 1 black, 2 white, 3 blue
_BLACK, _WHITE, _BLUE = 1, 2, 3


def _bitmap():
    px = [[0] * _W for _ in range(_H)]

    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[y][x] = c

    rect(4, 3, 20, 6, _BLACK)          # tab
    rect(5, 4, 19, 6, _WHITE)
    rect(4, 7, 43, 20, _BLACK)         # body
    rect(5, 8, 42, 19, _WHITE)
    rect(5, 8, 42, 10, _BLUE)          # lid shading
    rect(5, 21, 44, 21, _BLACK)        # shadow
    rect(44, 8, 44, 21, _BLACK)
    row_bytes = ((_W + 15) // 16) * 2
    planes = []
    for p in range(_DEPTH):
        out = bytearray()
        for y in range(_H):
            row = bytearray(row_bytes)
            for x in range(_W):
                if (px[y][x] >> p) & 1:
                    row[x // 8] |= 0x80 >> (x % 8)
            out += row
        planes.append(bytes(out))
    return b"".join(planes)


def drawer_icon() -> bytes:
    """A DiskObject of type WBDRAWER with a small folder image; placed automatically by Workbench."""
    gadget = struct.pack(">IhhhhHHHIIIiIHI",
                         0, 0, 0, _W, _H, 0x0005, 0x0003, 0x0001,
                         1, 0, 0, 0, 0, 0, 1)
    disk = struct.pack(">HH", 0xE310, 1) + gadget
    disk += struct.pack(">BBIIiiIIi", 2, 0, 0, 0, -0x80000000, -0x80000000, 1, 0, 0)
    drawer = struct.pack(">hhhhbbIIIIIIIhhhhH", 50, 50, 400, 100, -1, -1, 0, 0, 0, 0, 0, 0, 0,
                         0, 0, 0, 0, 1) + struct.pack(">ii", 0, 0)
    image = struct.pack(">hhhhhIBBI", 0, 0, _W, _H, _DEPTH, 1, 3, 0, 0)
    return disk + drawer + image + _bitmap()
