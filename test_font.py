#!/usr/bin/env python3
"""测试字体转换"""
import time
from font_to_swf import convert_font_to_swf

orig_swf_path = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\orig_unicode.swf"
ttf_path = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\simhei.ttf"
out_path = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\test_output.swf"

with open(orig_swf_path, 'rb') as f:
    orig_swf = f.read()
print(f"Original SWF: {len(orig_swf)} bytes")

def progress(msg):
    print(msg)

start = time.time()
result = convert_font_to_swf(ttf_path, orig_swf, progress)
elapsed = time.time() - start

with open(out_path, 'wb') as f:
    f.write(result)
print(f"Output: {out_path} ({len(result)} bytes, {len(result)/1024/1024:.1f} MB)")
print(f"Time: {elapsed:.1f}s")
