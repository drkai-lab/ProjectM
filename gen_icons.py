#!/usr/bin/env python3
"""Generate PWA icons (192x192 and 512x512) using only the standard library.

Draws a white circle on a #0381fe background and writes valid PNG files
without any external packages (no PIL). PNG encoding is done by hand with
zlib + struct.
"""
import os
import struct
import zlib

BG = (0x03, 0x81, 0xFE)   # #0381fe blue background
FG = (255, 255, 255)      # white circle


def make_chunk(chunk_type, data):
    """Build a PNG chunk: length + type + data + CRC32."""
    chunk_len = struct.pack('>I', len(data))
    crc = zlib.crc32(chunk_type + data) & 0xffffffff
    return chunk_len + chunk_type + data + struct.pack('>I', crc)


def create_png(width, height, filepath):
    cx = width / 2.0
    cy = height / 2.0
    r = 0.4 * min(width, height)
    r2 = r * r

    # Build raw scanlines: each row prefixed with filter byte 0 (None).
    rows = []
    bg = bytes(BG)
    fg = bytes(FG)
    for y in range(height):
        dy = y + 0.5 - cy
        dy2 = dy * dy
        row = bytearray()
        row.append(0)  # filter type: None
        for x in range(width):
            dx = x + 0.5 - cx
            if dx * dx + dy2 <= r2:
                row += fg
            else:
                row += bg
        rows.append(bytes(row))
    raw = b''.join(rows)

    # IHDR: width, height, bit depth 8, color type 2 (RGB), no interlace.
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    idat = make_chunk(b'IDAT', zlib.compress(raw, 9))
    iend = make_chunk(b'IEND', b'')

    png = b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend
    with open(filepath, 'wb') as f:
        f.write(png)


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(base, 'app', 'static', 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    for size in (192, 512):
        path = os.path.join(icons_dir, 'icon-%d.png' % size)
        create_png(size, size, path)
        print('Created %s (%d bytes)' % (path, os.path.getsize(path)))


if __name__ == '__main__':
    main()
