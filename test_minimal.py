#!/usr/bin/env python3
"""测试：生成所有字形为空的SWF，排除结构性问题"""
import struct, zlib
from font_to_swf import parse_swf_tags, build_swf_tag, build_swf_rect, BitWriter
from fontTools.ttLib import TTFont

orig_swf_path = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\orig_unicode.swf"
ttf_path = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\simhei.ttf"

with open(orig_swf_path, 'rb') as f:
    orig_swf = f.read()

orig = parse_swf_tags(orig_swf)
font = TTFont(ttf_path)
cmap = font.getBestCmap()
codepoints = sorted(cmap.keys())
hmtx = font['hmtx']
units_per_em = font['head'].unitsPerEm
scale = 20480.0 / units_per_em
os2 = font['OS/2']
ascent = round(abs(os2.sTypoAscender) * scale)
descent = round(abs(os2.sTypoDescender) * scale)
leading = round(abs(os2.sTypoLineGap) * scale)
num_glyphs = len(codepoints)

# 所有字形都用空shape
empty_bw = BitWriter()
empty_bw.write_ub(0, 4)
empty_bw.write_ub(0, 4)
empty_bw.write_ub(0, 6)
empty_shape = empty_bw.get_bytes()

# DefineFont3
df3 = bytearray()
df3 += struct.pack('<H', 1)  # FontID
df3.append(0x8C)  # Flags
df3.append(5)  # Lang
orig_name = b"Noto Sans CJK TC Regular"
df3.append(len(orig_name))
df3 += orig_name
df3 += struct.pack('<H', num_glyphs)

# OffsetTable
offset_table_size = num_glyphs * 4 + 4
current_offset = offset_table_size
for i in range(num_glyphs):
    df3 += struct.pack('<I', current_offset)
    current_offset += len(empty_shape)
df3 += struct.pack('<I', current_offset)  # CodeTableOffset

# ShapeTable
for i in range(num_glyphs):
    df3 += empty_shape

# CodeTable
for cp in codepoints:
    df3 += struct.pack('<H', min(cp, 0xFFFF))

# Layout
df3 += struct.pack('<h', ascent)
df3 += struct.pack('<h', descent)
df3 += struct.pack('<h', leading)

# AdvanceTable
for cp in codepoints:
    gn = cmap[cp]
    if gn in hmtx.metrics:
        aw = round(hmtx.metrics[gn][0] * scale)
    else:
        aw = round(units_per_em * scale)
    df3 += struct.pack('<h', min(aw, 32767))

# BoundsTable
for i in range(num_glyphs):
    df3 += build_swf_rect(0, 0, 0, 0)

# KerningCount
df3 += struct.pack('<H', 0)

# DefineFontAlignZones
align = bytearray()
align += struct.pack('<H', 1)
align.append(1 << 6)
for i in range(num_glyphs):
    align.append(2)
    align += struct.pack('<HH', 0, 0)
    align += struct.pack('<HH', 0, 0)
    align.append(0x03)

# 组装SWF
new_tags = bytearray()
for tag_type, tag_data in orig['tags']:
    if tag_type == 75:
        new_tags += build_swf_tag(75, bytes(df3))
    elif tag_type == 73:
        new_tags += build_swf_tag(73, bytes(align))
    else:
        new_tags += build_swf_tag(tag_type, tag_data)

body = bytearray()
body += orig['header_bytes']
body += new_tags
file_len = 8 + len(body)

swf = bytearray()
swf += b'FWS'
swf.append(orig['version'])
swf += struct.pack('<I', file_len)
swf += body

out_path = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\test_empty_glyphs.swf"
with open(out_path, 'wb') as f:
    f.write(swf)
print(f"Empty glyphs SWF: {len(swf)} bytes")
font.close()
