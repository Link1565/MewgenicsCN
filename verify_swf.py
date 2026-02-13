#!/usr/bin/env python3
"""对比原始和生成的SWF字体文件结构"""
import struct, zlib

def parse_swf(data, label=""):
    sig = data[:3].decode('ascii')
    ver = data[3]
    file_len = struct.unpack('<I', data[4:8])[0]
    
    if sig == 'CWS':
        body = data[:8] + zlib.decompress(data[8:])
    else:
        body = data
    
    print(f"\n=== {label} ===")
    print(f"Signature: {sig}, Version: {ver}, FileLen: {file_len}, ActualBodyLen: {len(body)}")
    
    pos = 8
    nbits = body[pos] >> 3
    total_bits = 5 + nbits * 4
    rect_bytes = (total_bits + 7) // 8
    rect_data = body[pos:pos+rect_bytes]
    pos += rect_bytes
    
    frame_rate = struct.unpack('<H', body[pos:pos+2])[0]
    frame_count = struct.unpack('<H', body[pos+2:pos+4])[0]
    pos += 4
    print(f"RECT: {rect_bytes} bytes, FrameRate: {frame_rate}, FrameCount: {frame_count}")
    
    tag_idx = 0
    while pos < len(body):
        if pos + 2 > len(body):
            print(f"  [TRUNCATED at pos {pos}]")
            break
        code_and_len = struct.unpack('<H', body[pos:pos+2])[0]
        tag_type = code_and_len >> 6
        tag_len = code_and_len & 0x3F
        pos += 2
        if tag_len == 0x3F:
            if pos + 4 > len(body):
                print(f"  [TRUNCATED reading long tag length at pos {pos}]")
                break
            tag_len = struct.unpack('<I', body[pos:pos+4])[0]
            pos += 4
        
        tag_data = body[pos:pos+tag_len]
        
        tag_names = {0:'End', 9:'SetBackgroundColor', 69:'FileAttributes', 
                     73:'DefineFontAlignZones', 75:'DefineFont3', 
                     88:'DefineFontName', 74:'CSMTextSettings', 1:'ShowFrame'}
        name = tag_names.get(tag_type, f'Tag{tag_type}')
        
        if tag_type == 75:
            # DefineFont3详细解析
            if len(tag_data) >= 6:
                font_id = struct.unpack('<H', tag_data[0:2])[0]
                flags = tag_data[2]
                lang = tag_data[3]
                name_len = tag_data[4]
                font_name = tag_data[5:5+name_len]
                has_layout = (flags >> 7) & 1
                wide_offsets = (flags >> 3) & 1
                wide_codes = (flags >> 2) & 1
                off = 5 + name_len
                num_glyphs = struct.unpack('<H', tag_data[off:off+2])[0]
                off += 2
                
                print(f"  [{tag_idx}] {name}: {tag_len} bytes")
                print(f"    FontID={font_id}, Flags=0x{flags:02X} (Layout={has_layout}, WideOff={wide_offsets}, WideCodes={wide_codes})")
                print(f"    Lang={lang}, Name='{font_name.decode('utf-8', errors='replace')}', NumGlyphs={num_glyphs}")
                
                # 检查offset table
                if wide_offsets:
                    offset_size = 4
                else:
                    offset_size = 2
                
                if num_glyphs > 0:
                    first_off = struct.unpack('<I' if wide_offsets else '<H', 
                                             tag_data[off:off+offset_size])[0]
                    expected_first = (num_glyphs + 1) * offset_size
                    print(f"    FirstOffset={first_off}, Expected={expected_first}")
                    
                    # 跳到code table offset
                    code_table_off_pos = off + num_glyphs * offset_size
                    code_table_off = struct.unpack('<I' if wide_offsets else '<H',
                                                   tag_data[code_table_off_pos:code_table_off_pos+offset_size])[0]
                    shape_data_start = off + (num_glyphs + 1) * offset_size
                    shape_data_end = off + code_table_off
                    code_table_start = shape_data_end
                    print(f"    ShapeData: offset {shape_data_start}-{shape_data_end} ({shape_data_end-shape_data_start} bytes)")
                    print(f"    CodeTable: offset {code_table_start}, size={num_glyphs*2} bytes")
                    
                    # 检查前几个code table entries
                    ct_off = code_table_start
                    codes = []
                    for i in range(min(5, num_glyphs)):
                        c = struct.unpack('<H', tag_data[ct_off:ct_off+2])[0]
                        codes.append(c)
                        ct_off += 2
                    print(f"    First codes: {codes} ({[chr(c) if 32<=c<128 else f'U+{c:04X}' for c in codes]})")
                    
                    if has_layout:
                        layout_off = ct_off + (num_glyphs - 5) * 2 if num_glyphs > 5 else ct_off
                        layout_off = code_table_start + num_glyphs * 2
                        ascent = struct.unpack('<h', tag_data[layout_off:layout_off+2])[0]
                        descent = struct.unpack('<h', tag_data[layout_off+2:layout_off+4])[0]
                        leading = struct.unpack('<h', tag_data[layout_off+4:layout_off+6])[0]
                        print(f"    Layout: ascent={ascent}, descent={descent}, leading={leading}")
                        
                        # 前几个advance widths
                        adv_off = layout_off + 6
                        advs = []
                        for i in range(min(5, num_glyphs)):
                            a = struct.unpack('<h', tag_data[adv_off:adv_off+2])[0]
                            advs.append(a)
                            adv_off += 2
                        print(f"    First advances: {advs}")
        elif tag_type == 73:
            font_id = struct.unpack('<H', tag_data[0:2])[0]
            csm = tag_data[2] >> 6
            print(f"  [{tag_idx}] {name}: {tag_len} bytes, FontID={font_id}, CSMHint={csm}")
        elif tag_type == 88:
            font_id = struct.unpack('<H', tag_data[0:2])[0]
            # 读取字体名（以null结尾的UTF-8）
            rest = tag_data[2:]
            null_pos = rest.find(b'\x00')
            if null_pos >= 0:
                fname = rest[:null_pos].decode('utf-8', errors='replace')
            else:
                fname = rest.decode('utf-8', errors='replace')
            print(f"  [{tag_idx}] {name}: {tag_len} bytes, FontID={font_id}, FontName='{fname}'")
        else:
            print(f"  [{tag_idx}] {name}: {tag_len} bytes")
        
        pos += tag_len
        tag_idx += 1
        if tag_type == 0:
            break

orig = open(r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\orig_unicode.swf", 'rb').read()
gen = open(r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\test_output.swf", 'rb').read()
parse_swf(orig, "ORIGINAL")
parse_swf(gen, "GENERATED")
