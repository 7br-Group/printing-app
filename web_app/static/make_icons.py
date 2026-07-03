import struct, zlib, os

def create_png(width, height, r, g, b):
    w, h = width, height
    raw = b''
    for _ in range(h):
        raw += b'\x00'  # filter byte
        for _ in range(w):
            raw += bytes([r, g, b, 255])  # RGBA
    
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc
    
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    idat_data = zlib.compress(raw)
    
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', ihdr)
    png += chunk(b'IDAT', idat_data)
    png += chunk(b'IEND', b'')
    return png

d = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(d, 'icon-192.png'), 'wb') as f:
    f.write(create_png(192, 192, 30, 41, 59))
with open(os.path.join(d, 'icon-512.png'), 'wb') as f:
    f.write(create_png(512, 512, 30, 41, 59))
print('Icons created')
