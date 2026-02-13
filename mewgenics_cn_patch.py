#!/usr/bin/env python3
"""
Mewgenics 中文补丁工具
直接从GPAK提取CSV，手动追加schinese列，保留原始CSV格式
"""
import struct
import json
import os
import sys
import re
import shutil
import time
import glob

VERSION = "20622"
BANNER = f"""
╔══════════════════════════════════════════╗
║     Mewgenics 中文补丁 v{VERSION}            ║
║     适用版本: Early Access (2025-2026)   ║
╚══════════════════════════════════════════╝
"""

# 可覆盖的语言列（让用户选择）
OVERRIDE_LANGUAGES = [
    ('pt-br', '巴西葡萄牙语'),
    ('it', '意大利语'),
    ('de', '德语'),
    ('fr', '法语'),
    ('sp', '西班牙语'),
]

# CSV文件名 -> 翻译JSON文件名的映射
CSV_TO_JSON = {
    "abilities.csv": "abilities.json",
    "additions.csv": "additions.json",
    "additions2.csv": "additions2.json",
    "additions3.csv": "additions3.json",
    "cutscene_text.csv": "cutscene_text.json",
    "enemy_abilities.csv": "enemy_abilities.json",
    "events.csv": "events.json",
    "furniture.csv": "furniture.json",
    "items.csv": "items.json",
    "keyword_tooltips.csv": "keyword_tooltips.json",
    "misc.csv": "misc.json",
    "mutations.csv": "mutations.json",
    "npc_dialog.csv": "npc_dialog.json",
    "passives.csv": "passives.json",
    "progression.csv": "progression.json",
    "pronouns.csv": "pronouns.json",
    "teamnames.csv": "teamnames.json",
    "units.csv": "units.json",
    "weather.csv": "weather.json",
}

def get_base_path():
    """获取补丁资源文件的根目录（支持PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def find_game_dir():
    """尝试自动查找游戏目录"""
    candidates = [os.getcwd()]
    # exe所在目录及其父级目录
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(exe_dir)
    candidates.append(os.path.dirname(exe_dir))
    candidates.append(os.path.dirname(os.path.dirname(exe_dir)))
    candidates += [
        r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
        r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
        r"E:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
        r"C:\Program Files\Steam\steamapps\common\Mewgenics",
        r"D:\SteamLibrary\steamapps\common\Mewgenics",
        r"E:\SteamLibrary\steamapps\common\Mewgenics",
    ]
    for path in candidates:
        if os.path.isfile(os.path.join(path, "resources.gpak")):
            return path
    return None

def read_gpak_index(fs):
    """读取GPAK文件索引"""
    file_count = struct.unpack('<I', fs.read(4))[0]
    entries = []
    for _ in range(file_count):
        name_len = struct.unpack('<H', fs.read(2))[0]
        if name_len == 0 or name_len > 500:
            raise ValueError("GPAK索引解析错误")
        name = fs.read(name_len).decode('utf-8')
        size = struct.unpack('<I', fs.read(4))[0]
        entries.append({'name': name, 'size': size})
    data_start = fs.tell()
    return entries, data_start

def extract_file_from_gpak(gpak_path, entries, data_start, target_name):
    """从GPAK提取指定文件的原始字节"""
    with open(gpak_path, 'rb') as f:
        f.seek(data_start)
        for entry in entries:
            if entry['name'] == target_name:
                return f.read(entry['size'])
            f.seek(f.tell() + entry['size'])
    return None

# 自动换行相关常量
_WRAP_MAX_WIDTH = 30  # 15个中文字符
_WRAP_BREAK_AFTER = set('。！？；：，、）】」』》~')
_WRAP_NO_LINE_START = set('。！？；：，、）】」』》~.!?,;:)]}\'\"')

def _display_width(text):
    """计算文本显示宽度（忽略格式标签）"""
    clean = re.sub(r'\[/?[^\]]*\]', '', text)
    clean = re.sub(r'\{[^\}]*\}', 'XX', clean)
    return sum(2 if ord(c) > 0x2E80 else 1 for c in clean)

def _is_inside_tag(text, pos):
    """检查位置是否在[...]或{...}标签内"""
    depth_sq = depth_br = 0
    for i in range(pos, -1, -1):
        if text[i] == ']': depth_sq += 1
        elif text[i] == '[':
            depth_sq -= 1
            if depth_sq < 0: return True
        elif text[i] == '}': depth_br += 1
        elif text[i] == '{':
            depth_br -= 1
            if depth_br < 0: return True
    return False

def _find_break_point(line):
    """在行内查找最佳断行位置（排除末尾字符，确保能拆分为两部分）"""
    end = len(line) - 2
    if end < 0:
        return -1
    start = max(0, end - 25)
    for j in range(end, start, -1):
        ch = line[j]
        if (ch in _WRAP_BREAK_AFTER or ch == ' ') and not _is_inside_tag(line, j):
            return j + 1
    for j in range(end, start, -1):
        if ord(line[j]) > 0x2E80 and line[j] not in _WRAP_NO_LINE_START and not _is_inside_tag(line, j):
            return j + 1
    return -1

def _wrap_single_line(text):
    """给单行长文本插入换行"""
    if _display_width(text) <= _WRAP_MAX_WIDTH:
        return text
    result = []
    line = ''
    width = 0
    in_tag = False
    tag_end_char = ''
    for i, c in enumerate(text):
        if not in_tag and c in '[{':
            in_tag = True
            tag_end_char = ']' if c == '[' else '}'
        is_end = in_tag and c == tag_end_char
        if is_end:
            in_tag = False
        if in_tag or c in '[]{}':
            line += c
            if is_end and re.search(r'\[img:[^\]]*\]$', line):
                width += 2
            continue
        width += 2 if ord(c) > 0x2E80 else 1
        line += c
        if width >= _WRAP_MAX_WIDTH and not in_tag:
            bp = _find_break_point(line)
            if bp > 0:
                while bp < len(line) and line[bp] in _WRAP_NO_LINE_START:
                    bp += 1
                if bp < len(line):
                    result.append(line[:bp])
                    line = line[bp:]
                    width = _display_width(line)
    if line:
        result.append(line)
    return '\n'.join(result)

def clean_control_chars(text):
    """清理控制字符：\r\n->\n，去除其他不可见控制字符"""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 去除除\n和\t外的控制字符（U+0000~U+001F）
    return re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', '', text)

def auto_wrap_text(text):
    """清理控制字符后对每一行应用自动换行"""
    text = clean_control_chars(text)
    return '\n'.join(_wrap_single_line(line) for line in text.split('\n'))

def csv_escape_field(value):
    """将值转义为CSV字段（仅在需要时加引号）"""
    if not value:
        return ''
    needs_quote = (',' in value or '"' in value or '\n' in value or '\r' in value)
    if needs_quote:
        return '"' + value.replace('"', '""') + '"'
    return value

def split_csv_fields(row_text):
    """将CSV行拆分为字段列表（正确处理引号），保留原始格式"""
    fields = []
    i = 0
    field_start = 0
    in_quote = False
    content = row_text.rstrip('\r\n')
    while i < len(content):
        ch = content[i]
        if ch == '"':
            in_quote = not in_quote
        elif ch == ',' and not in_quote:
            fields.append(content[field_start:i])
            field_start = i + 1
        i += 1
    fields.append(content[field_start:i])
    return fields

def split_csv_logical_rows(text):
    """将CSV文本分割为逻辑行（正确处理多行引号字段），保留原始行尾"""
    rows = []
    current = []
    in_quote = False
    i = 0
    line_start = 0

    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
        elif ch == '\n' and not in_quote:
            # 逻辑行结束（包含\n本身）
            rows.append(text[line_start:i+1])
            line_start = i + 1
        i += 1

    # 最后一行（可能没有换行符结尾）
    if line_start < len(text):
        rows.append(text[line_start:])
    return rows

def get_first_field(row_text):
    """从CSV行原始文本中提取第一个字段（KEY），不改变原始文本"""
    # KEY字段总是不带引号的简单字符串
    comma_pos = row_text.find(',')
    if comma_pos == -1:
        return row_text.strip()
    return row_text[:comma_pos].strip()

def get_en_field(row_text, en_col_idx):
    """从CSV行原始文本中提取en列的值"""
    field_idx = 0
    i = 0
    field_start = 0
    in_quote = False

    while i < len(row_text):
        ch = row_text[i]
        if ch == '"':
            in_quote = not in_quote
        elif ch == ',' and not in_quote:
            if field_idx == en_col_idx:
                raw = row_text[field_start:i]
                # 去掉引号
                if raw.startswith('"') and raw.endswith('"'):
                    return raw[1:-1].replace('""', '"')
                return raw
            field_idx += 1
            field_start = i + 1
        elif (ch == '\r' or ch == '\n') and not in_quote:
            break
        i += 1

    # 最后一个字段
    if field_idx == en_col_idx:
        raw = row_text[field_start:i].rstrip('\r\n')
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1].replace('""', '"')
        return raw
    return ''

def patch_csv_bytes(raw_bytes, translations, target_lang):
    """
    覆盖原始CSV中指定语言列的内容为中文翻译。
    返回 (patched_bytes, translated_count)。
    """
    # 检测BOM
    bom = b''
    data = raw_bytes
    if data.startswith(b'\xef\xbb\xbf'):
        bom = b'\xef\xbb\xbf'
        data = data[3:]

    text = data.decode('utf-8')

    # 检测换行符风格
    line_ending = '\r\n' if '\r\n' in text else '\n'

    # 分割为逻辑行
    rows = split_csv_logical_rows(text)
    if not rows:
        return raw_bytes, 0

    # 处理header行，找en列和目标语言列位置
    header = rows[0]
    header_stripped = header.rstrip('\r\n')
    header_fields = split_csv_fields(header_stripped)
    en_col_idx = 1
    target_col_idx = -1
    for idx, f in enumerate(header_fields):
        name = f.strip().lower()
        if name == 'en':
            en_col_idx = idx
        if name == target_lang:
            target_col_idx = idx

    # 构建输出
    output_parts = []
    # header保持不变（覆盖模式不改header）
    output_parts.append(header)

    # 处理数据行
    translated_count = 0
    for row in rows[1:]:
        row_stripped = row.rstrip('\r\n')
        row_ending = row[len(row_stripped):]

        # 空行或注释行
        trimmed = row_stripped.strip()
        if not trimmed or trimmed.startswith('//'):
            output_parts.append(row)
            continue

        # 提取KEY
        key = get_first_field(row_stripped)

        # 查找翻译
        if key and key in translations:
            cn_text = auto_wrap_text(translations[key])
            translated_count += 1
        else:
            cn_text = get_en_field(row_stripped, en_col_idx)

        cn_field = csv_escape_field(cn_text)

        if target_col_idx >= 0:
            # 覆盖目标列
            fields = split_csv_fields(row_stripped)
            while len(fields) <= target_col_idx:
                fields.append('')
            fields[target_col_idx] = cn_field
            output_parts.append(','.join(fields) + row_ending)
        else:
            # 回退：追加新列
            output_parts.append(row_stripped + ',' + cn_field + row_ending)

    result_text = ''.join(output_parts)
    return bom + result_text.encode('utf-8'), translated_count

def write_gpak(output_path, entries, data_start, original_gpak, patch_files):
    """写入新的GPAK文件"""
    with open(original_gpak, 'rb') as fs_in, open(output_path, 'wb') as fs_out:
        # 新索引
        new_entries = []
        for entry in entries:
            if entry['name'] in patch_files:
                new_entries.append({'name': entry['name'], 'size': len(patch_files[entry['name']])})
            else:
                new_entries.append({'name': entry['name'], 'size': entry['size']})

        # 写入文件数量
        fs_out.write(struct.pack('<I', len(new_entries)))

        # 写入索引
        for entry in new_entries:
            name_bytes = entry['name'].encode('utf-8')
            fs_out.write(struct.pack('<H', len(name_bytes)))
            fs_out.write(name_bytes)
            fs_out.write(struct.pack('<I', entry['size']))

        # 写入文件数据
        fs_in.seek(data_start)
        total = len(entries)
        patched_count = 0
        buf_size = 1024 * 1024

        for i, entry in enumerate(entries):
            if entry['name'] in patch_files:
                fs_out.write(patch_files[entry['name']])
                fs_in.seek(fs_in.tell() + entry['size'])
                patched_count += 1
            else:
                remaining = entry['size']
                while remaining > 0:
                    to_read = min(remaining, buf_size)
                    data = fs_in.read(to_read)
                    if not data:
                        raise IOError(f"GPAK数据读取异常: 文件 '{entry['name']}' 剩余 {remaining} 字节未读取，可能文件已损坏")
                    fs_out.write(data)
                    remaining -= len(data)

            if (i + 1) % 2000 == 0 or i == total - 1:
                pct = (i + 1) / total * 100
                print(f"\r  进度: {pct:.1f}% ({i+1}/{total})", end='', flush=True)

        print()
        return patched_count

def update_settings(game_dir, lang='schinese'):
    """更新游戏设置语言"""
    appdata = os.environ.get('APPDATA', '')
    settings_base = os.path.join(appdata, 'Glaiel Games', 'Mewgenics')
    if not os.path.isdir(settings_base):
        print("  [跳过] 未找到游戏设置目录（首次运行游戏后再执行）")
        return False

    updated = False
    for steam_dir in os.listdir(settings_base):
        settings_path = os.path.join(settings_base, steam_dir, 'settings.txt')
        if os.path.isfile(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'current_language' in content:
                new_content = re.sub(
                    r'current_language\s+\S+',
                    f'current_language {lang}',
                    content
                )
                if new_content != content:
                    with open(settings_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"  [已更新] {settings_path}")
                    updated = True
                else:
                    target_name = '中文' if lang == 'schinese' else lang
                    print(f"  [已是{target_name}] {settings_path}")
                    updated = True
            else:
                with open(settings_path, 'a', encoding='utf-8') as f:
                    f.write(f'\ncurrent_language = {lang}\n')
                print(f"  [已添加] {settings_path}")
                updated = True
    return updated

def generate_reset_bat(game_dir):
    """在游戏目录生成语言重置脚本，游戏更新后可快速修复"""
    bat_content = '''@echo off
chcp 65001 >nul
echo 正在重置游戏语言设置...
set "BASE=%APPDATA%\\Glaiel Games\\Mewgenics"
if not exist "%BASE%" (
    echo 未找到游戏设置目录
    pause
    exit /b 1
)
for /d %%D in ("%BASE%\\*") do (
    if exist "%%D\\settings.txt" (
        powershell -Command "(Get-Content '%%D\\settings.txt') -replace 'current_language\\s+schinese','current_language en' | Set-Content '%%D\\settings.txt'"
        echo   已重置: %%D\\settings.txt
    )
)
echo.
echo 语言已重置为英文。请重新运行中文补丁工具来重新打补丁。
pause
'''
    bat_path = os.path.join(game_dir, '重置语言.bat')
    try:
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)
        print(f"  已生成语言重置脚本: {bat_path}")
    except Exception:
        pass

def check_language_mismatch(game_dir, gpak_path, entries, data_start):
    """检测语言设置与GPAK是否匹配（游戏更新后可能不匹配）"""
    # 检查设置是否为schinese
    appdata = os.environ.get('APPDATA', '')
    settings_base = os.path.join(appdata, 'Glaiel Games', 'Mewgenics')
    is_schinese = False
    if os.path.isdir(settings_base):
        for d in os.listdir(settings_base):
            sp = os.path.join(settings_base, d, 'settings.txt')
            if os.path.isfile(sp):
                with open(sp, 'r', encoding='utf-8') as f:
                    if re.search(r'current_language\s+schinese', f.read()):
                        is_schinese = True
                        break
    if not is_schinese:
        return False
    # 检查GPAK是否已打补丁
    test_csv = extract_file_from_gpak(gpak_path, entries, data_start, 'data/text/additions.csv')
    if test_csv:
        header = test_csv.decode('utf-8-sig').split('\n')[0]
        if 'schinese' not in header:
            return True  # 语言不匹配
    return False

def main():
    print(BANNER)

    # 查找游戏目录
    game_dir = find_game_dir()
    if not game_dir:
        print("未能自动检测到游戏目录。")
        game_dir = input("请输入Mewgenics游戏目录路径: ").strip().strip('"')
        if not os.path.isfile(os.path.join(game_dir, "resources.gpak")):
            print("[错误] 指定目录中未找到 resources.gpak")
            input("按回车键退出...")
            return 1

    gpak_path = os.path.join(game_dir, "resources.gpak")
    print(f"游戏目录: {game_dir}")
    print(f"GPAK文件: {gpak_path}")
    gpak_size = os.path.getsize(gpak_path) / (1024*1024*1024)
    print(f"GPAK大小: {gpak_size:.2f} GB")
    print()

    # 加载翻译JSON
    base_path = get_base_path()
    trans_dir = os.path.join(base_path, 'translations')
    if not os.path.isdir(trans_dir):
        print(f"[错误] 未找到翻译数据目录: {trans_dir}")
        input("按回车键退出...")
        return 1

    all_translations = {}
    print("加载翻译文件:")
    for csv_name, json_name in CSV_TO_JSON.items():
        json_path = os.path.join(trans_dir, json_name)
        if os.path.isfile(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                trans = json.load(f)
            all_translations[csv_name] = trans
            print(f"  {json_name}: {len(trans)} 条翻译")
        else:
            print(f"  [缺失] {json_name}")
    print()

    # 备份原始GPAK（必须在读取索引之前，确保有干净的原始文件）
    backup_path = gpak_path + '.bak'
    if not os.path.isfile(backup_path):
        print("正在备份原始GPAK...")
        shutil.copy2(gpak_path, backup_path)
        print(f"  备份已保存: {backup_path}")
    else:
        print(f"  备份已存在: {backup_path}")

    # 始终从备份（原始GPAK）读取索引，避免从已打补丁的文件读取
    source_gpak = backup_path if os.path.isfile(backup_path) else gpak_path
    print(f"正在读取GPAK索引（源: {os.path.basename(source_gpak)}）...")
    with open(source_gpak, 'rb') as fs:
        entries, data_start = read_gpak_index(fs)
    print(f"  文件总数: {len(entries)}")

    # 让用户选择覆盖哪个语言列
    print("请选择要覆盖的语言列（中文将替换该语言）：")
    print("  提示：覆盖现有语言可避免游戏更新后报语言错误")
    for i, (code, name) in enumerate(OVERRIDE_LANGUAGES):
        print(f"  {i+1}. {code} ({name})")
    print()
    lang_choice = input(f"请选择 [1-{len(OVERRIDE_LANGUAGES)}]，默认为1: ").strip()
    try:
        lang_idx = int(lang_choice) - 1
    except ValueError:
        lang_idx = 0
    if lang_idx < 0 or lang_idx >= len(OVERRIDE_LANGUAGES):
        lang_idx = 0
    target_lang, target_name = OVERRIDE_LANGUAGES[lang_idx]
    print(f"  将覆盖: {target_lang} ({target_name})")
    print()

    # 从LGPAK提取CSV并注入翻译
    print("正在处理CSV文件...")
    patch_files = {}
    total_translated = 0

    for entry in entries:
        name = entry['name']
        if not name.startswith('data/text/') or not name.endswith('.csv'):
            continue

        csv_name = os.path.basename(name)
        translations = all_translations.get(csv_name, {})

        # 从原始GPAK提取CSV
        raw_bytes = extract_file_from_gpak(source_gpak, entries, data_start, name)
        if raw_bytes is None:
            continue

        # 覆盖目标语言列
        patched_bytes, trans_count = patch_csv_bytes(raw_bytes, translations, target_lang)
        patch_files[name] = patched_bytes
        total_translated += trans_count

        orig_kb = len(raw_bytes) / 1024
        new_kb = len(patched_bytes) / 1024
        print(f"  {csv_name}: {orig_kb:.1f}KB -> {new_kb:.1f}KB ({trans_count} 条翻译)")

    print(f"  总计翻译: {total_translated} 条")
    print()

    # 字体替换（可选）
    font_files = []
    # exe所在目录（非PyInstaller临时目录）
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    for ext in ('*.ttf', '*.otf'):
        font_files.extend(glob.glob(os.path.join(exe_dir, ext)))

    if font_files:
        print("检测到字体文件（可替换游戏中文字体）:")
        print("  0. 不替换字体（使用默认）")
        for i, fp in enumerate(font_files, 1):
            fname = os.path.basename(fp)
            fsize = os.path.getsize(fp) / (1024*1024)
            print(f"  {i}. {fname} ({fsize:.1f} MB)")
        print()
        choice = input(f"请选择字体 [0-{len(font_files)}]: ").strip()
        try:
            choice_idx = int(choice)
        except ValueError:
            choice_idx = 0

        if 1 <= choice_idx <= len(font_files):
            selected_font = font_files[choice_idx - 1]
            print(f"\n正在转换字体: {os.path.basename(selected_font)}")
            print("（这可能需要1-3分钟，请耐心等待...）")
            try:
                from font_to_swf import convert_font_to_swf
                # 从GPAK提取原始unicodefont.swf
                orig_swf = extract_file_from_gpak(source_gpak, entries, data_start, 'swfs/unicodefont.swf')
                if orig_swf:
                    def font_progress(msg):
                        print(f"  {msg}")
                    new_swf = convert_font_to_swf(selected_font, orig_swf, font_progress)
                    patch_files['swfs/unicodefont.swf'] = new_swf
                    print(f"  字体转换完成: {len(new_swf)/1024/1024:.1f} MB")
                else:
                    print("  [错误] 无法从GPAK提取原始字体文件")
            except Exception as e:
                print(f"  [错误] 字体转换失败: {e}")
                import traceback
                traceback.print_exc()
                print("  将继续使用默认字体...")
            print()
    print()

    print()

    # 写入新GPAK
    output_path = gpak_path + '.new'
    print("正在生成补丁GPAK...")
    start_time = time.time()
    patched = write_gpak(output_path, entries, data_start, source_gpak, patch_files)
    elapsed = time.time() - start_time
    out_size = os.path.getsize(output_path) / (1024*1024*1024)
    print(f"  替换了 {patched} 个文件")
    print(f"  输出大小: {out_size:.2f} GB")
    print(f"  耗时: {elapsed:.1f} 秒")
    print()

    # 替换原文件
    print("正在应用补丁...")
    try:
        os.replace(output_path, gpak_path)
        print("  [成功] resources.gpak 已更新")
    except Exception as e:
        print(f"  [错误] 无法替换文件: {e}")
        print(f"  请手动将 {output_path} 重命名为 resources.gpak")
        input("按回车键退出...")
        return 1
    print()

    # 更新游戏语言设置
    print(f"正在设置游戏语言为 {target_lang}...")
    update_settings(game_dir, target_lang)
    print()

    # 记录覆盖的语言，供恢复工具使用
    lang_record = os.path.join(game_dir, '.cn_patch_lang')
    try:
        with open(lang_record, 'w') as f:
            f.write(target_lang)
    except Exception:
        pass

    print("=" * 44)
    print("  补丁安装完成！启动游戏即可体验中文。")
    print(f"  已覆盖 {target_lang}({target_name}) 列。")
    print("  游戏更新后重新运行补丁即可，不会报错。")
    print("  如需完全恢复，运行恢复工具。")
    print("=" * 44)
    print()
    input("按回车键退出...")
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[致命错误] {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
        sys.exit(1)
