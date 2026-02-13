#!/usr/bin/env python3
"""测试：将指定SWF注入到已打补丁的GPAK中"""
import struct, os, sys

def inject_swf(gpak_path, swf_path):
    new_swf = open(swf_path, 'rb').read()
    
    with open(gpak_path, 'rb') as f:
        file_count = struct.unpack('<I', f.read(4))[0]
        entries = []
        for _ in range(file_count):
            nl = struct.unpack('<H', f.read(2))[0]
            name = f.read(nl).decode('utf-8')
            size = struct.unpack('<I', f.read(4))[0]
            entries.append({'name': name, 'size': size})
        data_start = f.tell()
    
    # 找到unicodefont.swf的位置
    target = 'swfs/unicodefont.swf'
    out_path = gpak_path + '.fonttest'
    
    with open(gpak_path, 'rb') as fin, open(out_path, 'wb') as fout:
        # 写入文件头
        fout.write(struct.pack('<I', file_count))
        for e in entries:
            name_bytes = e['name'].encode('utf-8')
            fout.write(struct.pack('<H', len(name_bytes)))
            fout.write(name_bytes)
            if e['name'] == target:
                fout.write(struct.pack('<I', len(new_swf)))
            else:
                fout.write(struct.pack('<I', e['size']))
        
        # 写入数据
        fin.seek(data_start)
        for e in entries:
            orig_data = fin.read(e['size'])
            if e['name'] == target:
                fout.write(new_swf)
                print(f"  替换 {target}: {e['size']} -> {len(new_swf)} bytes")
            else:
                fout.write(orig_data)
    
    os.replace(out_path, gpak_path)
    print(f"  已写入: {gpak_path}")

if __name__ == '__main__':
    gpak = r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\resources.gpak"
    swf = sys.argv[1] if len(sys.argv) > 1 else r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\MewgenicsCN\test_empty_glyphs.swf"
    print(f"注入: {swf}")
    inject_swf(gpak, swf)
    print("完成！启动游戏测试")
