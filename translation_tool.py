#!/usr/bin/env python3
"""
咪咪汉化工具箱 - 通用AI翻译工具
集成文本读取、多供应商AI翻译、手动编辑、补丁应用等功能
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import struct
import json
import json_repair
import os
import sys
import re
import shutil
import time
import glob
import threading
import warnings
warnings.filterwarnings("ignore", message=".*timestamp.*")

VERSION = "1.0"

# AI供应商预设 (名称, base_url, 默认模型列表)
AI_PROVIDERS = [
    ('智谱AI (Zhipu)', 'https://open.bigmodel.cn/api/paas/v4', ['glm-4-flash', 'glm-4-plus', 'glm-4-long', 'glm-4-flashx']),
    ('DeepSeek', 'https://api.deepseek.com', ['deepseek-chat', 'deepseek-reasoner']),
    ('通义千问 (Qwen)', 'https://dashscope.aliyuncs.com/compatible-mode/v1', ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwen-long']),
    ('Moonshot/Kimi', 'https://api.moonshot.cn/v1', ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k']),
    ('硅基流动 (SiliconFlow)', 'https://api.siliconflow.cn/v1', []),
    ('OpenAI', 'https://api.openai.com/v1', ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1-nano']),
    ('自定义 (Custom)', '', []),
]

# 游戏 CSV 中的中文列名
CN_TARGET_LANG = 'schinese'

# 不允许AI翻译覆盖的特殊key（语言配置等）
PROTECTED_KEYS = {
    'CURRENT_LANGUAGE_NAME': '简体中文',
    'CURRENT_LANGUAGE_SHIPPABLE': 'yes',
}

# 叙事类文件（使用不同翻译风格）
NARRATIVE_FILES = {"npc_dialog.csv", "events.csv", "cutscene_text.csv", "progression.csv"}

# 默认翻译提示词
DEFAULT_SYSTEM_PROMPT = """你是一位深谙中文互联网文化的游戏本地化翻译高手。

## 游戏背景
你正在翻译 Mewgenics —— 一款由 Edmund McMillen（《以撒的结合力》《超级肉肉哥》作者）和 Tyler Glaiel 开发的回合制猫咪战术肉鸽游戏。
- 背景设定在 Boon County（福恩郡），玩家繁殖、培养变异猫咪军团，派它们去冒险战斗
- 风格延续以撒系列的黑色幽默、怪诞恶趣味：血腥、屎尿屁、药丸、诡异变异一个不少
- 10+职业（战士/坦克/法师等）、1000+技能、900+物品，战术深度极高
- 猫咪可以繁殖遗传，传递变异、技能和基因特征，越养越离谱

## 翻译风格要求
1. **说人话**：翻译出来要像一个中国玩家自己写的攻略/描述，不是翻译腔。读起来顺口自然，一个中国人日常就会这么说
2. **有梗但不硬凑**：可以适当融入中文互联网语感（比如"逆天""上大分""纯纯的XX""血赚""直接起飞"等），但必须贴合语境，不要为了玩梗而玩梗
3. **贴合黑色幽默基调**：这游戏本身就很癫，翻译可以大胆一点，恶趣味该到位就到位，别把原文的骚话翻成正经八百的书面语
4. **技能描述简洁有力**：技能/物品描述要言简意赅，像游戏内提示一样干脆利落，不要又臭又长
5. **对话要有角色感**：NPC对话、事件文本要有角色性格，英文俚语要意译不要直译（如 elbow grease→卖力干活，not the sharpest tool→脑子不太好使）

## 绝对禁止
- ❌ "吃伤""吃到伤害"——说"受到伤害"或"挨打"
- ❌ "使得""令其""予以"等文言翻译腔
- ❌ "该单位""此效果"等机翻味表述——直接说"它""这个效果"
- ❌ 无意义的"的"字堆砌
- ❌ 翻译占位符和格式标签（必须原样保留）

## 格式规则（严格遵守）
- 保留所有格式标签：[img:xxx]、[b]...[/b]、[s:数字]...[/s] 等
- 保留所有占位符：{stacks}、{catname}、{he}、{his}、{him}、{applier} 等
- 保留换行位置
- 只输出翻译结果，不要解释

## 核心术语表（必须统一）
Shield=护盾, Thorns=荆棘, Brace=硬抗, Bleed=流血, Burn=灼烧, Poison=中毒
Blind=致盲, Freeze=冻结, Stun=眩晕, Fear=恐惧, Madness=狂暴, Confusion=混乱
Charmed=魅惑, Immobile=定身, Knockback=击退, Dodge=闪避, Lifesteal=吸血
Health Regen=生命恢复, Mana Regen=法力恢复, Charge=蓄能, Bruise=淤伤
Cleave=劈砍, Petrify=石化, Doomed=末日, Hex=咒术, Exhaustion=疲劳
Constitution=体质, Intelligence=智力, Dexterity=敏捷, Charisma=魅力
Luck=幸运, Strength=力量, Familiar=使魔, Champion=勇者, Elite=精英, Alpha=头领
Bounty=悬赏, Counter Attack=反击, Reflect=反射, Rot=腐烂, Mutation=变异
Passive=被动, Ability=技能, Spell=法术, Basic Attack=普攻, Ranged=远程, Melee=近战
Tile=格, Round=回合, Turn=回合, Downed=倒下, Corpse=尸体
Buff=增益, Debuff=减益, Crit=暴击, Stack=层, Leeches=水蛭"""


# ==================== GPAK/CSV工具函数 ====================

def find_game_dir():
    """自动查找游戏目录（优先Steam安装目录，再找相对路径）"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    # 优先搜索Steam安装目录
    steam_candidates = []
    for drive in 'CDEFG':
        steam_candidates.append(rf"{drive}:\Program Files (x86)\Steam\steamapps\common\Mewgenics")
        steam_candidates.append(rf"{drive}:\SteamLibrary\steamapps\common\Mewgenics")
    # 再搜索exe相对路径
    relative_candidates = [
        os.getcwd(),
        exe_dir,
        os.path.dirname(exe_dir),
        os.path.dirname(os.path.dirname(exe_dir)),
    ]
    for path in steam_candidates + relative_candidates:
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
    """从GPAK提取指定文件"""
    with open(gpak_path, 'rb') as f:
        f.seek(data_start)
        for entry in entries:
            if entry['name'] == target_name:
                return f.read(entry['size'])
            f.seek(f.tell() + entry['size'])
    return None


def split_csv_fields(row_text):
    """CSV行拆分为字段列表"""
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


def unquote_csv_field(raw):
    """去除CSV字段的引号"""
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('""', '"')
    return raw


def split_csv_logical_rows(text):
    """CSV文本分割为逻辑行"""
    rows = []
    in_quote = False
    i = 0
    line_start = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
        elif ch == '\n' and not in_quote:
            rows.append(text[line_start:i + 1])
            line_start = i + 1
        i += 1
    if line_start < len(text):
        rows.append(text[line_start:])
    return rows


def csv_escape_field(value):
    """值转义为CSV字段"""
    if not value:
        return ''
    if ',' in value or '"' in value or '\n' in value or '\r' in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def get_first_field(row_text):
    """提取CSV行的第一个字段（KEY）"""
    comma_pos = row_text.find(',')
    if comma_pos == -1:
        return row_text.strip()
    return row_text[:comma_pos].strip()


def extract_all_languages(gpak_path):
    """从GPAK提取所有CSV的所有语言列
    返回 {csv_name: {KEY: {lang: text}}}
    """
    with open(gpak_path, 'rb') as fs:
        entries, data_start = read_gpak_index(fs)

    all_data = {}
    for entry in entries:
        name = entry['name']
        if not name.startswith('data/text/') or not name.endswith('.csv'):
            continue
        csv_name = os.path.basename(name)
        raw = extract_file_from_gpak(gpak_path, entries, data_start, name)
        if not raw:
            continue

        text = raw.decode('utf-8-sig')
        rows = split_csv_logical_rows(text)
        if not rows:
            continue

        header_fields = split_csv_fields(rows[0].rstrip('\r\n'))
        lang_cols = {}
        for idx, f in enumerate(header_fields):
            col_name = f.strip().lower()
            if idx == 0 or col_name in ('notes', '') :
                continue
            lang_cols[idx] = col_name

        csv_data = {}
        for row in rows[1:]:
            row_stripped = row.rstrip('\r\n').strip()
            if not row_stripped or row_stripped.startswith('//'):
                continue
            fields = split_csv_fields(row_stripped)
            if not fields:
                continue
            key = unquote_csv_field(fields[0])
            if not key:
                continue
            langs = {}
            for col_idx, lang_name in lang_cols.items():
                if col_idx < len(fields):
                    val = unquote_csv_field(fields[col_idx])
                    if val:
                        langs[lang_name] = val
            csv_data[key] = langs
        all_data[csv_name] = csv_data

    return all_data, entries, data_start


# ==================== 自动换行 ====================

_WRAP_MAX_WIDTH = 20
_WRAP_BREAK_AFTER = set('。！？；：，、）】」』》~')
_WRAP_NO_LINE_START = set('。！？；：，、）】」』》~.!?,;:)]}\'\"')

def _display_width(text):
    clean = re.sub(r'\[/?[^\]]*\]', '', text)
    clean = re.sub(r'\{[^\}]*\}', 'XX', clean)
    return sum(2 if ord(c) > 0x2E80 else 1 for c in clean)

def _is_inside_tag(text, pos):
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

def _wrap_single_line(text, max_width=None):
    if max_width is None:
        max_width = _WRAP_MAX_WIDTH
    if _display_width(text) <= max_width:
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
        if width >= max_width and not in_tag:
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
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', '', text)

def auto_wrap_text(text, wrap_width=None):
    """自动换行，wrap_width=None表示不换行"""
    text = clean_control_chars(text)
    if wrap_width is None:
        return text
    return '\n'.join(_wrap_single_line(line, wrap_width) for line in text.split('\n'))


# ==================== 补丁相关 ====================

def patch_csv_bytes(raw_bytes, translations, target_lang=CN_TARGET_LANG, wrap_width=None):
    """将中文翻译写入CSV的指定语言列"""
    bom = b''
    data = raw_bytes
    if data.startswith(b'\xef\xbb\xbf'):
        bom = b'\xef\xbb\xbf'
        data = data[3:]
    text = data.decode('utf-8')
    line_ending = '\r\n' if '\r\n' in text else '\n'
    rows = split_csv_logical_rows(text)
    if not rows:
        return raw_bytes, 0

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

    output_parts = [header]
    translated_count = 0
    for row in rows[1:]:
        row_stripped = row.rstrip('\r\n')
        row_ending = row[len(row_stripped):]
        trimmed = row_stripped.strip()
        if not trimmed or trimmed.startswith('//'):
            output_parts.append(row)
            continue
        key = get_first_field(row_stripped)
        if key and key in translations:
            cn_text = auto_wrap_text(translations[key], wrap_width)
            translated_count += 1
        else:
            # 无翻译时用英文填充
            fields = split_csv_fields(row_stripped)
            cn_text = unquote_csv_field(fields[en_col_idx]) if en_col_idx < len(fields) else ''
        cn_field = csv_escape_field(cn_text)
        if target_col_idx >= 0:
            fields = split_csv_fields(row_stripped)
            while len(fields) <= target_col_idx:
                fields.append('')
            fields[target_col_idx] = cn_field
            output_parts.append(','.join(fields) + row_ending)
        else:
            output_parts.append(row_stripped + ',' + cn_field + row_ending)

    result_text = ''.join(output_parts)
    return bom + result_text.encode('utf-8'), translated_count


def write_gpak(output_path, entries, data_start, original_gpak, patch_files, progress_cb=None):
    """写入新GPAK文件"""
    with open(original_gpak, 'rb') as fs_in, open(output_path, 'wb') as fs_out:
        new_entries = []
        for entry in entries:
            if entry['name'] in patch_files:
                new_entries.append({'name': entry['name'], 'size': len(patch_files[entry['name']])})
            else:
                new_entries.append({'name': entry['name'], 'size': entry['size']})
        fs_out.write(struct.pack('<I', len(new_entries)))
        for entry in new_entries:
            name_bytes = entry['name'].encode('utf-8')
            fs_out.write(struct.pack('<H', len(name_bytes)))
            fs_out.write(name_bytes)
            fs_out.write(struct.pack('<I', entry['size']))
        fs_in.seek(data_start)
        total = len(entries)
        buf_size = 1024 * 1024
        for i, entry in enumerate(entries):
            if entry['name'] in patch_files:
                fs_out.write(patch_files[entry['name']])
                fs_in.seek(fs_in.tell() + entry['size'])
            else:
                remaining = entry['size']
                while remaining > 0:
                    to_read = min(remaining, buf_size)
                    d = fs_in.read(to_read)
                    if not d:
                        raise IOError(f"GPAK数据读取异常: 文件 '{entry['name']}' 剩余 {remaining} 字节未读取，可能文件已损坏")
                    fs_out.write(d)
                    remaining -= len(d)
            if progress_cb and ((i + 1) % 500 == 0 or i == total - 1):
                progress_cb(i + 1, total)
    return len(patch_files)


def _find_settings_dirs(game_dir=None):
    """查找所有可能的游戏设置目录（兼容Windows/Linux/Steam Deck）"""
    candidates = []
    # Windows: %APPDATA%/Glaiel Games/Mewgenics
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        candidates.append(os.path.join(appdata, 'Glaiel Games', 'Mewgenics'))
    # Linux原生: ~/.local/share/Glaiel Games/Mewgenics
    home = os.path.expanduser('~')
    candidates.append(os.path.join(home, '.local', 'share', 'Glaiel Games', 'Mewgenics'))
    # Steam Deck / Proton: 从游戏安装目录推断compatdata路径
    if game_dir:
        # 游戏路径形如 .../steamapps/common/Mewgenics
        # compatdata在 .../steamapps/compatdata/<appid>/pfx/drive_c/users/steamuser/AppData/Roaming/
        parts = os.path.normpath(game_dir).split(os.sep)
        for i, part in enumerate(parts):
            if part.lower() == 'steamapps':
                steamapps = os.sep.join(parts[:i+1])
                compat_base = os.path.join(steamapps, 'compatdata')
                if os.path.isdir(compat_base):
                    for app_id in os.listdir(compat_base):
                        proton_path = os.path.join(
                            compat_base, app_id, 'pfx', 'drive_c', 'users', 'steamuser',
                            'AppData', 'Roaming', 'Glaiel Games', 'Mewgenics')
                        candidates.append(proton_path)
                break
    # 去重并返回存在的目录
    seen = set()
    result = []
    for c in candidates:
        c = os.path.normpath(c)
        if c not in seen and os.path.isdir(c):
            seen.add(c)
            result.append(c)
    return result


def update_settings(game_dir, lang):
    """更新游戏设置语言，返回 ('updated'|'already'|'not_found', [路径列表])"""
    settings_bases = _find_settings_dirs(game_dir)
    found_files = []
    updated = False
    already = False
    for settings_base in settings_bases:
        for steam_dir in os.listdir(settings_base):
            settings_path = os.path.join(settings_base, steam_dir, 'settings.txt')
            if not os.path.isfile(settings_path):
                continue
            found_files.append(settings_path)
            with open(settings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'current_language' in content:
                new_content = re.sub(r'current_language\s+\S+', f'current_language {lang}', content)
                if new_content != content:
                    with open(settings_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    updated = True
                else:
                    already = True
            else:
                with open(settings_path, 'a', encoding='utf-8') as f:
                    f.write(f'\ncurrent_language {lang}\n')
                updated = True
    if updated:
        return 'updated', found_files
    if already:
        return 'already', found_files
    return 'not_found', found_files


# ==================== GUI主界面 ====================

class TranslationToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"咪咪汉化工具箱 v{VERSION}")
        self.root.geometry("1200x950")
        self.root.minsize(900, 600)

        # 数据存储
        self.game_dir = None
        self.gpak_path = None
        self.entries = None
        self.data_start = None
        # {csv_name: {key: {lang: text}}} — 从GPAK读取的多语言数据
        self.all_data = {}
        # {csv_name: {key: cn_text}} — 中文翻译
        self.translations = {}
        # 当前选中的文件
        self.current_file = None
        # 表格当前显示的数据keys（用于跟踪行）
        self.table_keys = []
        # AI翻译线程控制
        self.translate_running = False
        self.translate_stop_event = threading.Event()
        # Token用量统计
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

        self._build_ui()
        # 尝试自动定位游戏目录
        detected = find_game_dir()
        if detected:
            self.game_dir_var.set(detected)

    def _build_ui(self):
        """构建界面"""
        # === 顶部：游戏目录 ===
        top = ttk.Frame(self.root, padding=5)
        top.pack(fill='x')
        ttk.Label(top, text="游戏目录:").pack(side='left')
        self.game_dir_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.game_dir_var, width=70).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(top, text="浏览", command=self._browse_game_dir).pack(side='left', padx=2)

        # === 标签页 ===
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self._build_tab_text()
        self._build_tab_translate()
        self._build_tab_patch()

        # === 底部状态栏 ===
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken', anchor='w', padding=3)
        status_bar.pack(fill='x', side='bottom')

    # ---------- Tab1: 文本管理 ----------
    def _build_tab_text(self):
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text="  文本管理  ")

        # 工具栏
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill='x', pady=(0, 5))
        ttk.Button(toolbar, text="从游戏读取文本", command=self._read_gpak).pack(side='left', padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=8, fill='y')
        ttk.Label(toolbar, text="文件:").pack(side='left')
        self.file_combo_var = tk.StringVar()
        self.file_combo = ttk.Combobox(toolbar, textvariable=self.file_combo_var, state='readonly', width=25)
        self.file_combo.pack(side='left', padx=2)
        self.file_combo.bind('<<ComboboxSelected>>', self._on_file_selected)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=8, fill='y')
        ttk.Label(toolbar, text="搜索:").pack(side='left')
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side='left', padx=2)
        search_entry.bind('<Return>', lambda e: self._filter_table())
        ttk.Button(toolbar, text="搜索", command=self._filter_table).pack(side='left', padx=2)
        ttk.Button(toolbar, text="清除", command=self._clear_filter).pack(side='left', padx=2)

        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=8, fill='y')
        self.untranslated_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="只显示未翻译", variable=self.untranslated_only_var,
                         command=self._refresh_table).pack(side='left', padx=2)

        # 统计信息
        self.stats_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self.stats_var).pack(side='right', padx=5)

        # 表格区域
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill='both', expand=True)

        # 使用Treeview做表格
        columns = ('no', 'key', 'en', 'cn')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='browse')
        self.tree.heading('no', text='#', anchor='center')
        self.tree.heading('key', text='KEY', anchor='w')
        self.tree.heading('en', text='English', anchor='w')
        self.tree.heading('cn', text='中文翻译', anchor='w')
        self.tree.column('no', width=50, minwidth=40, anchor='center', stretch=False)
        self.tree.column('key', width=250, minwidth=150)
        self.tree.column('en', width=380, minwidth=200)
        self.tree.column('cn', width=380, minwidth=200)

        # 滚动条
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        # 双击编辑
        self.tree.bind('<Double-1>', self._on_tree_double_click)

        # 编辑区域
        edit_frame = ttk.LabelFrame(tab, text="编辑翻译", padding=5)
        edit_frame.pack(fill='x', pady=(5, 0))
        self.edit_key_var = tk.StringVar()
        ttk.Label(edit_frame, text="KEY:").grid(row=0, column=0, sticky='w')
        ttk.Entry(edit_frame, textvariable=self.edit_key_var, state='readonly', width=40).grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(edit_frame, text="英文:").grid(row=0, column=2, sticky='w', padx=(15, 0))
        self.edit_en_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_en_var, state='readonly', width=50).grid(row=0, column=3, sticky='we', padx=5)

        ttk.Label(edit_frame, text="中文:").grid(row=1, column=0, sticky='w', pady=(5, 0))
        self.edit_cn_text = tk.Text(edit_frame, height=3, width=80, wrap='word')
        self.edit_cn_text.grid(row=1, column=1, columnspan=3, sticky='we', padx=5, pady=(5, 0))

        ttk.Button(edit_frame, text="保存", command=self._save_edit).grid(row=1, column=4, sticky='w', padx=5, pady=(5, 0))
        edit_frame.columnconfigure(3, weight=1)

    # ---------- Tab2: AI翻译 ----------
    def _build_tab_translate(self):
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text="  AI翻译  ")

        # 配置区
        config = ttk.LabelFrame(tab, text="AI配置", padding=10)
        config.pack(fill='x', pady=(0, 5))

        # Row 0: 供应商选择
        ttk.Label(config, text="AI供应商:").grid(row=0, column=0, sticky='w')
        self.provider_var = tk.StringVar()
        self.provider_combo = ttk.Combobox(config, textvariable=self.provider_var, state='readonly', width=25)
        self.provider_combo['values'] = [p[0] for p in AI_PROVIDERS]
        self.provider_combo.current(0)
        self.provider_combo.grid(row=0, column=1, sticky='w', padx=5)
        self.provider_combo.bind('<<ComboboxSelected>>', self._on_provider_changed)

        # Row 1: Base URL
        ttk.Label(config, text="API地址:").grid(row=1, column=0, sticky='w', pady=(5, 0))
        self.base_url_var = tk.StringVar(value=AI_PROVIDERS[0][1])
        self.base_url_entry = ttk.Entry(config, textvariable=self.base_url_var, width=55)
        self.base_url_entry.grid(row=1, column=1, columnspan=2, sticky='we', padx=5, pady=(5, 0))

        # Row 2: API Key
        ttk.Label(config, text="API密钥:").grid(row=2, column=0, sticky='w', pady=(5, 0))
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(config, textvariable=self.api_key_var, width=50, show='*')
        self.api_key_entry.grid(row=2, column=1, sticky='we', padx=5, pady=(5, 0))
        self.btn_toggle_key = ttk.Button(config, text="显示", command=self._toggle_api_key, width=6)
        self.btn_toggle_key.grid(row=2, column=2, padx=2, pady=(5, 0))

        # Row 3: 模型选择 + 获取模型列表按钮
        ttk.Label(config, text="模型:").grid(row=3, column=0, sticky='w', pady=(5, 0))
        model_frame = ttk.Frame(config)
        model_frame.grid(row=3, column=1, columnspan=2, sticky='we', padx=5, pady=(5, 0))
        self.model_var = tk.StringVar(value='')
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, width=30)
        self.model_combo['values'] = []
        self.model_combo.pack(side='left')
        ttk.Button(model_frame, text="获取模型列表", command=self._fetch_models).pack(side='left', padx=5)

        # Row 4: 温度
        ttk.Label(config, text="温度(temperature):").grid(row=4, column=0, sticky='w', pady=(5, 0))
        temp_frame = ttk.Frame(config)
        temp_frame.grid(row=4, column=1, columnspan=2, sticky='we', padx=5, pady=(5, 0))
        self.temperature_var = tk.StringVar(value='0.3')
        ttk.Spinbox(temp_frame, from_=0.0, to=2.0, increment=0.1, textvariable=self.temperature_var, width=8, format='%.1f').pack(side='left')
        ttk.Label(temp_frame, text='(部分模型仅支持特定值，具体请查询服务商文档)', foreground='gray').pack(side='left', padx=10)

        # Row 5: 线程数 + 跳过已翻译
        ttk.Label(config, text="并发线程:").grid(row=5, column=0, sticky='w', pady=(5, 0))
        opt_frame = ttk.Frame(config)
        opt_frame.grid(row=5, column=1, columnspan=2, sticky='we', padx=5, pady=(5, 0))
        self.threads_var = tk.StringVar(value='3')
        ttk.Spinbox(opt_frame, from_=1, to=50, textvariable=self.threads_var, width=8).pack(side='left')
        ttk.Label(opt_frame, text="批量大小:").pack(side='left', padx=(15, 0))
        self.batch_size_var = tk.StringVar(value='10')
        ttk.Spinbox(opt_frame, from_=1, to=50, textvariable=self.batch_size_var, width=8).pack(side='left', padx=(5, 0))
        ttk.Label(opt_frame, text="翻译模式:").pack(side='left', padx=(15, 0))
        self.translate_mode_var = tk.StringVar(value='添加（跳过已翻译）')
        mode_combo = ttk.Combobox(opt_frame, textvariable=self.translate_mode_var, state='readonly', width=20)
        mode_combo['values'] = ['添加（跳过已翻译）', '覆盖（重翻所有）']
        mode_combo.pack(side='left', padx=(5, 0))

        config.columnconfigure(1, weight=1)

        # 翻译提示词（可编辑）
        prompt_frame = ttk.LabelFrame(tab, text="翻译提示词（System Prompt）", padding=5)
        prompt_frame.pack(fill='x', pady=(0, 5))
        self.prompt_text = tk.Text(prompt_frame, height=6, wrap='word')
        self.prompt_text.pack(fill='x', side='left', expand=True)
        prompt_sb = ttk.Scrollbar(prompt_frame, orient='vertical', command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=prompt_sb.set)
        prompt_sb.pack(side='right', fill='y')
        # 填充默认提示词
        self.prompt_text.insert('1.0', DEFAULT_SYSTEM_PROMPT)

        # 文件选择（动态填充，加载文本后才显示）
        self.translate_file_frame = ttk.LabelFrame(tab, text="选择要翻译的文件", padding=5)
        self.translate_file_frame.pack(fill='x', pady=(0, 5))
        self.translate_file_vars = {}
        self.translate_file_inner = ttk.Frame(self.translate_file_frame)
        self.translate_file_inner.pack(fill='x')
        self.translate_hint = ttk.Label(self.translate_file_inner, text="请先在「文本管理」中加载文本数据", foreground='gray')
        self.translate_hint.pack(pady=10)
        # 全选/全不选按钮
        self.translate_btn_frame = ttk.Frame(self.translate_file_frame)
        self.translate_btn_frame.pack(fill='x')
        ttk.Button(self.translate_btn_frame, text="全选", command=lambda: self._set_all_translate(True)).pack(side='left', padx=5)
        ttk.Button(self.translate_btn_frame, text="全不选", command=lambda: self._set_all_translate(False)).pack(side='left', padx=5)
        self.translate_btn_frame.pack_forget()

        # 控制按钮
        ctrl = ttk.Frame(tab)
        ctrl.pack(fill='x', pady=5)
        self.btn_start_translate = ttk.Button(ctrl, text="▶ 开始翻译", command=self._start_translate)
        self.btn_start_translate.pack(side='left', padx=5)
        self.btn_stop_translate = ttk.Button(ctrl, text="■ 停止", command=self._stop_translate, state='disabled')
        self.btn_stop_translate.pack(side='left', padx=5)

        # 进度条区域
        progress_frame = ttk.Frame(tab)
        progress_frame.pack(fill='x', pady=(0, 3))
        # 当前文件进度
        ttk.Label(progress_frame, text="当前文件:").pack(side='left', padx=(5, 2))
        self.translate_progress_var = tk.DoubleVar(value=0)
        self.translate_progress = ttk.Progressbar(progress_frame, variable=self.translate_progress_var, maximum=100, length=200)
        self.translate_progress.pack(side='left', padx=(0, 5))
        self.translate_pct_var = tk.StringVar(value="")
        ttk.Label(progress_frame, textvariable=self.translate_pct_var).pack(side='left')
        # 总进度
        ttk.Label(progress_frame, text="  总进度:").pack(side='left', padx=(10, 2))
        self.translate_total_progress_var = tk.DoubleVar(value=0)
        self.translate_total_progress = ttk.Progressbar(progress_frame, variable=self.translate_total_progress_var, maximum=100, length=200)
        self.translate_total_progress.pack(side='left', padx=(0, 5))
        self.translate_total_pct_var = tk.StringVar(value="")
        ttk.Label(progress_frame, textvariable=self.translate_total_pct_var).pack(side='left')

        # Token统计区
        token_frame = ttk.Frame(tab)
        token_frame.pack(fill='x', pady=(0, 3))
        self.token_stats_var = tk.StringVar(value="Token用量: 输入 0 | 输出 0 | 合计 0")
        ttk.Label(token_frame, textvariable=self.token_stats_var, foreground='#555').pack(side='left', padx=5)

        # 日志区
        log_frame = ttk.LabelFrame(tab, text="翻译日志", padding=5)
        log_frame.pack(fill='both', expand=True)
        self.translate_log = tk.Text(log_frame, height=10, state='disabled', wrap='word')
        log_sb = ttk.Scrollbar(log_frame, orient='vertical', command=self.translate_log.yview)
        self.translate_log.configure(yscrollcommand=log_sb.set)
        self.translate_log.pack(side='left', fill='both', expand=True)
        log_sb.pack(side='right', fill='y')

    # ---------- Tab3: 打补丁 ----------
    def _build_tab_patch(self):
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text="  打补丁  ")

        # CSV文件目录
        csv_frame = ttk.LabelFrame(tab, text="CSV文件目录", padding=10)
        csv_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(csv_frame, text="CSV目录:").grid(row=0, column=0, sticky='w')
        self.csv_dir_var = tk.StringVar()
        ttk.Entry(csv_frame, textvariable=self.csv_dir_var, width=55).grid(row=0, column=1, sticky='we', padx=5)
        ttk.Button(csv_frame, text="浏览", command=self._browse_csv_dir).grid(row=0, column=2, padx=2)
        ttk.Label(csv_frame, text="AI翻译会自动保存到此目录的CSV文件中（schinese列）", foreground='gray').grid(row=1, column=1, columnspan=2, sticky='w', padx=5)
        csv_frame.columnconfigure(1, weight=1)

        # 翻译设置
        trans_frame = ttk.LabelFrame(tab, text="游戏内设置", padding=10)
        trans_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(trans_frame, text="游戏内换行字数:").grid(row=0, column=0, sticky='w')
        self.wrap_width_var = tk.StringVar(value='15')
        ttk.Spinbox(trans_frame, from_=0, to=50, textvariable=self.wrap_width_var, width=6).grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(trans_frame, text="(0=不换行，根据需要合理设置)", foreground='gray').grid(row=0, column=2, sticky='w')

        # 字体选择
        font_frame = ttk.LabelFrame(tab, text="字体设置", padding=10)
        font_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(font_frame, text="字体文件 (.ttf/.otf):").grid(row=0, column=0, sticky='w')
        self.font_path_var = tk.StringVar()
        ttk.Entry(font_frame, textvariable=self.font_path_var, width=55).grid(row=0, column=1, sticky='we', padx=5)
        ttk.Button(font_frame, text="浏览", command=self._browse_font).grid(row=0, column=2, padx=2)
        ttk.Label(font_frame, text="留空则不替换字体，使用游戏默认字体", foreground='gray').grid(row=1, column=1, sticky='w', padx=5)
        font_frame.columnconfigure(1, weight=1)

        # 要替换的CSV文件列表
        patch_file_frame = ttk.LabelFrame(tab, text="要替换的CSV文件（勾选的文件将写入游戏）", padding=5)
        patch_file_frame.pack(fill='x', pady=(0, 5))
        # 全选/全不选按钮
        patch_sel_frame = ttk.Frame(patch_file_frame)
        patch_sel_frame.pack(fill='x')
        ttk.Button(patch_sel_frame, text="全选", command=lambda: self._set_all_patch(True)).pack(side='left', padx=5)
        ttk.Button(patch_sel_frame, text="全不选", command=lambda: self._set_all_patch(False)).pack(side='left', padx=5)
        ttk.Button(patch_sel_frame, text="刷新列表", command=self._refresh_patch_files).pack(side='left', padx=5)
        # 滚动区域
        patch_canvas = tk.Canvas(patch_file_frame, height=120)
        patch_sb = ttk.Scrollbar(patch_file_frame, orient='vertical', command=patch_canvas.yview)
        self.patch_file_inner = ttk.Frame(patch_canvas)
        self.patch_file_inner.bind('<Configure>', lambda e: patch_canvas.configure(scrollregion=patch_canvas.bbox('all')))
        patch_canvas.create_window((0, 0), window=self.patch_file_inner, anchor='nw')
        patch_canvas.configure(yscrollcommand=patch_sb.set)
        patch_canvas.pack(side='left', fill='both', expand=True)
        patch_sb.pack(side='right', fill='y')
        self.patch_file_vars = {}

        # 操作按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', pady=5)
        ttk.Button(btn_frame, text="🔧 应用补丁（CSV→游戏）", command=self._apply_patch).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="🔄 还原补丁", command=self._restore_patch).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="🛠 修复游戏语言配置", command=self._fix_game_language).pack(side='left', padx=10)

        # 补丁进度
        self.patch_progress_var = tk.DoubleVar(value=0)
        self.patch_progress = ttk.Progressbar(btn_frame, variable=self.patch_progress_var, maximum=100, length=300)
        self.patch_progress.pack(side='left', padx=10, fill='x', expand=True)

        # 日志
        patch_log_frame = ttk.LabelFrame(tab, text="操作日志", padding=5)
        patch_log_frame.pack(fill='both', expand=True)
        self.patch_log = tk.Text(patch_log_frame, height=15, state='disabled', wrap='word')
        patch_log_sb = ttk.Scrollbar(patch_log_frame, orient='vertical', command=self.patch_log.yview)
        self.patch_log.configure(yscrollcommand=patch_log_sb.set)
        self.patch_log.pack(side='left', fill='both', expand=True)
        patch_log_sb.pack(side='right', fill='y')

    # ==================== Tab1 事件处理 ====================

    def _browse_game_dir(self):
        path = filedialog.askdirectory(title="选择Mewgenics游戏目录")
        if path:
            if os.path.isfile(os.path.join(path, "resources.gpak")):
                self.game_dir_var.set(path)
            else:
                messagebox.showerror("错误", "所选目录中未找到 resources.gpak")

    def _read_gpak(self):
        """从GPAK读取所有多语言文本"""
        game_dir = self.game_dir_var.get().strip()
        if not game_dir:
            messagebox.showwarning("提示", "请先设置游戏目录")
            return
        gpak_path = os.path.join(game_dir, "resources.gpak")
        bak_path = gpak_path + '.bak'
        # 优先读取备份（原始未打补丁的GPAK）
        read_path = bak_path if os.path.isfile(bak_path) else gpak_path
        if not os.path.isfile(read_path):
            messagebox.showerror("错误", f"未找到 {read_path}")
            return

        self.game_dir = game_dir
        self.gpak_path = gpak_path
        self.status_var.set("正在读取GPAK...")
        self.root.update()

        def do_read():
            try:
                all_data, entries, data_start = extract_all_languages(read_path)
                self.all_data = all_data
                self.entries = entries
                self.data_start = data_start

                # 自动导出CSV并从中加载已有翻译
                csv_dir = self._get_csv_dir()
                self._export_csvs_to_dir(read_path, entries, data_start, csv_dir)
                self._load_translations_from_csvs(csv_dir)

                self.root.after(0, self._on_gpak_loaded)
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda m=err_msg: messagebox.showerror("错误", f"读取GPAK失败:\n{m}"))
                self.root.after(0, lambda: self.status_var.set("读取失败"))

        threading.Thread(target=do_read, daemon=True).start()

    def _count_translatable(self, csv_name):
        """统计某CSV中可翻译条数（英文非空的行）"""
        csv_data = self.all_data.get(csv_name, {})
        return sum(1 for langs in csv_data.values() if langs.get('en', ''))

    def _on_gpak_loaded(self):
        """GPAK读取完成回调"""
        total_keys = sum(self._count_translatable(n) for n in self.all_data)
        total_cn = sum(len(v) for v in self.translations.values())
        file_names = []
        for csv_name in sorted(self.all_data.keys()):
            cn_count = len(self.translations.get(csv_name, {}))
            total = self._count_translatable(csv_name)
            file_names.append(f"{csv_name} ({cn_count}/{total})")
        self.file_combo['values'] = file_names
        if file_names:
            self.file_combo.current(0)
            self._on_file_selected(None)
        self.status_var.set(f"已读取 {len(self.all_data)} 个文件，{total_keys} 条可翻译文本，{total_cn} 条已翻译")
        # 刷新AI翻译页和补丁页的文件列表
        self._refresh_translate_files()
        self._refresh_patch_files()

    def _refresh_translate_files(self):
        """根据已加载的数据动态刷新AI翻译页的文件列表"""
        # 清除旧内容
        for w in self.translate_file_inner.winfo_children():
            w.destroy()
        self.translate_file_vars.clear()

        if not self.all_data:
            ttk.Label(self.translate_file_inner, text="请先在「文本管理」中加载文本数据", foreground='gray').pack(pady=10)
            self.translate_btn_frame.pack_forget()
            return

        # 动态生成checkbox列表（分多列）
        col = 0
        row = 0
        max_rows = max(10, (len(self.all_data) + 2) // 3)
        for csv_name in sorted(self.all_data.keys()):
            cn_count = len(self.translations.get(csv_name, {}))
            total = self._count_translatable(csv_name)
            label = f"{csv_name} ({cn_count}/{total})"
            var = tk.BooleanVar(value=True)
            self.translate_file_vars[csv_name] = var
            ttk.Checkbutton(self.translate_file_inner, text=label, variable=var).grid(row=row, column=col, sticky='w', padx=5)
            row += 1
            if row >= max_rows:
                row = 0
                col += 1
        # 显示全选/全不选按钮
        self.translate_btn_frame.pack(fill='x', pady=(5, 0))

    def _get_csv_dir(self):
        """获取CSV文件目录"""
        # 优先使用补丁tab中用户设置的目录
        if hasattr(self, 'csv_dir_var') and self.csv_dir_var.get().strip():
            d = self.csv_dir_var.get().strip()
            os.makedirs(d, exist_ok=True)
            return d
        # 默认：游戏目录下的csv_export
        if self.game_dir:
            d = os.path.join(self.game_dir, 'csv_export')
        elif getattr(sys, 'frozen', False):
            d = os.path.join(os.path.dirname(sys.executable), 'csv_export')
        else:
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv_export')
        os.makedirs(d, exist_ok=True)
        # 同步到补丁tab的目录设置
        if hasattr(self, 'csv_dir_var'):
            self.csv_dir_var.set(d)
        return d

    def _export_csvs_to_dir(self, gpak_path, entries, data_start, csv_dir):
        """从GPAK导出所有CSV到指定目录（如果目录中已有同名文件则跳过）"""
        os.makedirs(csv_dir, exist_ok=True)
        for entry in entries:
            name = entry['name']
            if not name.startswith('data/text/') or not name.endswith('.csv'):
                continue
            csv_name = os.path.basename(name)
            out_path = os.path.join(csv_dir, csv_name)
            if os.path.isfile(out_path):
                continue  # 已存在则不覆盖（保留用户修改）
            raw_bytes = extract_file_from_gpak(gpak_path, entries, data_start, name)
            if raw_bytes:
                with open(out_path, 'wb') as f:
                    f.write(raw_bytes)

    def _load_translations_from_csvs(self, csv_dir):
        """从SV文件中加载已有的中文翻译（检测schinese列中的中文字符）"""
        if not os.path.isdir(csv_dir):
            return
        for fname in os.listdir(csv_dir):
            if not fname.endswith('.csv'):
                continue
            csv_path = os.path.join(csv_dir, fname)
            try:
                with open(csv_path, 'rb') as f:
                    raw = f.read()
                data = raw.lstrip(b'\xef\xbb\xbf').decode('utf-8')
                rows = split_csv_logical_rows(data)
                if not rows:
                    continue
                header_fields = split_csv_fields(rows[0].rstrip('\r\n'))
                target_col = -1
                for idx, field in enumerate(header_fields):
                    if field.strip().lower() == CN_TARGET_LANG:
                        target_col = idx
                        break
                if target_col < 0:
                    continue
                trans = {}
                for row in rows[1:]:
                    stripped = row.rstrip('\r\n').strip()
                    if not stripped or stripped.startswith('//'):
                        continue
                    key = get_first_field(stripped)
                    if not key:
                        continue
                    fields = split_csv_fields(stripped)
                    if target_col < len(fields):
                        val = unquote_csv_field(fields[target_col]).strip()
                        # 受保护的key使用固定值
                        if key in PROTECTED_KEYS:
                            trans[key] = PROTECTED_KEYS[key]
                        elif val:
                            trans[key] = val
                if trans:
                    # 合并：CSV数据为基础，内存中已有的翻译优先保留
                    existing = self.translations.get(fname, {})
                    trans.update(existing)
                    self.translations[fname] = trans
            except Exception:
                continue

    def _on_file_selected(self, event):
        """文件下拉框选择变更"""
        sel = self.file_combo_var.get()
        if not sel:
            return
        csv_name = sel.split(' (')[0]
        if csv_name not in self.all_data:
            return
        self.current_file = csv_name
        self._refresh_table()

    def _refresh_table(self):
        """刷新表格数据"""
        self.tree.delete(*self.tree.get_children())
        self.table_keys = []
        if not self.current_file or self.current_file not in self.all_data:
            return
        csv_data = self.all_data[self.current_file]
        cn_data = self.translations.get(self.current_file, {})
        search = self.search_var.get().strip().lower()
        total = 0
        translated = 0
        row_no = 0
        for key, langs in csv_data.items():
            en = langs.get('en', '')
            cn = cn_data.get(key, '')
            # 英文为空的行不计入统计，也不算未翻译
            if not en.strip():
                if self.untranslated_only_var.get():
                    continue
            else:
                total += 1
                if cn:
                    translated += 1
                # 只显示未翻译过滤
                if self.untranslated_only_var.get() and cn:
                    continue
            # 搜索过滤
            if search:
                if search not in key.lower() and search not in en.lower() and search not in cn.lower():
                    continue
            row_no += 1
            # 截断显示（避免超长文本卡UI）
            en_display = en.replace('\n', '↵ ')[:200]
            cn_display = cn.replace('\n', '↵ ')[:200]
            self.tree.insert('', 'end', values=(row_no, key, en_display, cn_display))
            self.table_keys.append(key)

        self.stats_var.set(f"已翻译: {translated}/{total}")

    def _filter_table(self):
        self._refresh_table()

    def _clear_filter(self):
        self.search_var.set('')
        self.untranslated_only_var.set(False)
        self._refresh_table()

    def _on_tree_double_click(self, event):
        """双击表格行，加载到编辑区"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, 'values')
        if not values:
            return
        key = values[1]
        csv_data = self.all_data.get(self.current_file, {})
        langs = csv_data.get(key, {})
        en = langs.get('en', '')
        cn = self.translations.get(self.current_file, {}).get(key, '')

        self.edit_key_var.set(key)
        self.edit_en_var.set(en)
        self.edit_cn_text.delete('1.0', 'end')
        self.edit_cn_text.insert('1.0', cn)
        self._editing_item = item

    def _save_edit(self):
        """保存单条编辑"""
        key = self.edit_key_var.get()
        if not key or not self.current_file:
            return
        cn_text = self.edit_cn_text.get('1.0', 'end').strip()
        if self.current_file not in self.translations:
            self.translations[self.current_file] = {}
        self.translations[self.current_file][key] = cn_text

        # 更新表格显示
        if hasattr(self, '_editing_item') and self._editing_item:
            old_vals = self.tree.item(self._editing_item, 'values')
            row_no = old_vals[0]
            en_display = old_vals[2]
            cn_display = cn_text.replace('\n', '↵ ')[:200]
            self.tree.item(self._editing_item, values=(row_no, key, en_display, cn_display))

        # 直接保存到CSV文件
        self._auto_save_translations(self.current_file)
        self.status_var.set(f"已保存: {key}")

    def _save_all(self):
        """保存所有翻译到CSV文件（schinese列）"""
        if not self.translations:
            messagebox.showwarning("提示", "没有可保存的翻译")
            return
        csv_dir = self._get_csv_dir()
        wrap_chars = int(self.wrap_width_var.get()) if hasattr(self, 'wrap_width_var') else 10
        wrap_width = wrap_chars * 2 if wrap_chars > 0 else None
        count = 0
        total_trans = 0
        for csv_name, trans in self.translations.items():
            if not trans:
                continue
            csv_path = os.path.join(csv_dir, csv_name)
            if not os.path.isfile(csv_path):
                continue
            with open(csv_path, 'rb') as f:
                raw_bytes = f.read()
            patched_bytes, trans_count = patch_csv_bytes(raw_bytes, trans, CN_TARGET_LANG, wrap_width)
            with open(csv_path, 'wb') as f:
                f.write(patched_bytes)
            count += 1
            total_trans += trans_count
        self.status_var.set(f"已保存 {total_trans} 条翻译到 {count} 个CSV文件 ({csv_dir})")

    # ==================== Tab2 AI翻译 ====================

    def _on_provider_changed(self, event=None):
        """供应商切换时更新base_url和模型列表"""
        sel = self.provider_var.get()
        for name, url, models in AI_PROVIDERS:
            if name == sel:
                self.base_url_var.set(url)
                self.model_combo['values'] = models
                # 自定义供应商允许编辑URL
                if '自定义' in name or 'Custom' in name:
                    self.base_url_entry.configure(state='normal')
                else:
                    self.base_url_entry.configure(state='normal')
                break

    def _toggle_api_key(self):
        """切换API密钥显示/隐藏"""
        if self.api_key_entry.cget('show') == '*':
            self.api_key_entry.configure(show='')
            self.btn_toggle_key.configure(text='隐藏')
        else:
            self.api_key_entry.configure(show='*')
            self.btn_toggle_key.configure(text='显示')

    def _create_client(self):
        """创建OpenAI兼容客户端"""
        import httpx
        from openai import OpenAI
        api_key = self.api_key_var.get().strip()
        base_url = self.base_url_var.get().strip()
        if not api_key:
            raise ValueError("请输入API密钥")
        if not base_url:
            raise ValueError("请输入API地址")
        return OpenAI(
            api_key=api_key, base_url=base_url,
            http_client=httpx.Client(
                limits=httpx.Limits(max_connections=200, max_keepalive_connections=100),
                timeout=httpx.Timeout(120.0, connect=30.0),
            ),
        )

    def _get_client_config(self):
        """获取客户端配置参数（用于多线程各自创建独立client）"""
        api_key = self.api_key_var.get().strip()
        base_url = self.base_url_var.get().strip()
        if not api_key:
            raise ValueError("请输入API密钥")
        if not base_url:
            raise ValueError("请输入API地址")
        return {'api_key': api_key, 'base_url': base_url}

    def _create_thread_client(self, config):
        """为当前线程创建独立的OpenAI客户端"""
        import httpx
        from openai import OpenAI
        return OpenAI(
            api_key=config['api_key'], base_url=config['base_url'],
            http_client=httpx.Client(
                timeout=httpx.Timeout(120.0, connect=30.0),
            ),
        )

    def _fetch_models(self):
        """从API获取可用模型列表"""
        try:
            client = self._create_client()
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return
        self.status_var.set("正在获取模型列表...")
        self.root.update()

        def do_fetch():
            try:
                models_resp = client.models.list()
                model_ids = sorted([m.id for m in models_resp.data])
                def update_ui():
                    self.model_combo['values'] = model_ids
                    if model_ids:
                        self.model_var.set(model_ids[0])
                    self.status_var.set(f"获取到 {len(model_ids)} 个模型")
                    messagebox.showinfo("模型列表", f"共 {len(model_ids)} 个模型:\n\n" + '\n'.join(model_ids[:30]) + ('\n...' if len(model_ids) > 30 else ''))
                self.root.after(0, update_ui)
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda m=err_msg: messagebox.showerror("获取失败", f"无法获取模型列表:\n{m}"))
                self.root.after(0, lambda: self.status_var.set("获取模型列表失败"))

        threading.Thread(target=do_fetch, daemon=True).start()

    def _set_all_translate(self, val):
        for v in self.translate_file_vars.values():
            v.set(val)

    def _log_translate(self, msg):
        """写翻译日志"""
        def _do():
            self.translate_log.configure(state='normal')
            self.translate_log.insert('end', msg + '\n')
            self.translate_log.see('end')
            self.translate_log.configure(state='disabled')
        self.root.after(0, _do)

    def _update_token_stats(self, prompt_tokens=0, completion_tokens=0):
        """更新Token统计（线程安全）"""
        if not hasattr(self, '_token_lock'):
            self._token_lock = threading.Lock()
        with self._token_lock:
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        text = f"Token用量: 输入 {self.total_prompt_tokens:,} | 输出 {self.total_completion_tokens:,} | 合计 {self.total_tokens:,}"
        self.root.after(0, lambda: self.token_stats_var.set(text))

    def _start_translate(self):
        """开始AI翻译"""
        if not self.all_data:
            messagebox.showwarning("提示", "请先在「文本管理」中从游戏读取文本")
            return
        try:
            client_config = self._get_client_config()
            # 验证配置有效（创建一个测试client）
            test_client = self._create_thread_client(client_config)
            del test_client
        except Exception as e:
            messagebox.showwarning("配置错误", str(e))
            return

        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("提示", "请选择或输入模型名称")
            return

        threads = int(self.threads_var.get())
        batch_size = int(self.batch_size_var.get())
        # 翻译模式：添加=跳过已翻译，覆盖=重翻所有
        skip_existing = '添加' in self.translate_mode_var.get()
        temperature = float(self.temperature_var.get())

        selected_files = [csv for csv, var in self.translate_file_vars.items() if var.get()]
        if not selected_files:
            messagebox.showwarning("提示", "请至少选择一个文件")
            return

        # 重置token统计
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self._update_token_stats()

        # 重置进度条
        self.translate_progress_var.set(0)
        self.translate_pct_var.set("")
        self.translate_total_progress_var.set(0)
        self.translate_total_pct_var.set("")

        self.translate_running = True
        self.translate_stop_event.clear()
        self.btn_start_translate.configure(state='disabled')
        self.btn_stop_translate.configure(state='normal')

        # 读取用户编辑的提示词
        user_prompt = self.prompt_text.get('1.0', 'end').strip()
        if not user_prompt:
            messagebox.showwarning("提示", "翻译提示词不能为空")
            return

        provider_name = self.provider_var.get()
        mode_text = '添加' if skip_existing else '覆盖'
        self._log_translate(f"供应商: {provider_name} | 模型: {model} | 温度: {temperature} | 线程: {threads} | 批量: {batch_size} | 模式: {mode_text}")

        # 翻译状态对象（传参用，避免闭包）
        ctx = {
            'client_config': client_config, 'model': model, 'temperature': temperature,
            'sys_prompt': user_prompt, 'batch_size': batch_size,
        }
        # 线程本地存储：每个线程独立的client
        self._thread_local = threading.local()

        def worker():
            from concurrent.futures import ThreadPoolExecutor, as_completed
            total_done = 0
            total_err = 0
            total_skip = 0

            # 预先计算所有文件的总待翻译数
            grand_total = 0
            for csv_name in selected_files:
                if csv_name not in self.all_data:
                    continue
                csv_data = self.all_data[csv_name]
                cn_data = self.translations.get(csv_name, {})
                for key, langs in csv_data.items():
                    en = langs.get('en', '')
                    if not en:
                        continue
                    if skip_existing and key in cn_data and cn_data[key]:
                        continue
                    grand_total += 1
            global_done = [0]

            def _update_total_progress():
                """更新总进度条"""
                if grand_total > 0:
                    pct = global_done[0] / grand_total * 100
                    self.root.after(0, lambda p=pct: self.translate_total_progress_var.set(p))
                    self.root.after(0, lambda p=pct, d=global_done[0], t=grand_total: self.translate_total_pct_var.set(f"{d}/{t} ({p:.0f}%)"))

            self._log_translate(f"总计待翻译: {grand_total} 条")

            # 创建全局线程池（复用，而非每个文件创建一个）
            executor = ThreadPoolExecutor(max_workers=threads)

            try:
                for csv_name in selected_files:
                    if self.translate_stop_event.is_set():
                        break
                    if csv_name not in self.all_data:
                        continue
                    csv_data = self.all_data[csv_name]
                    cn_data = self.translations.get(csv_name, {})

                    # 重置当前文件进度
                    self.root.after(0, lambda: self.translate_progress_var.set(0))
                    self.root.after(0, lambda n=csv_name: self.translate_pct_var.set(f"{n}"))

                    to_translate = {}
                    for key, langs in csv_data.items():
                        en = langs.get('en', '')
                        if not en:
                            continue
                        # 受保护的key使用固定值，不交给AI翻译
                        if key in PROTECTED_KEYS:
                            if csv_name not in self.translations:
                                self.translations[csv_name] = {}
                            self.translations[csv_name][key] = PROTECTED_KEYS[key]
                            total_skip += 1
                            continue
                        if skip_existing and key in cn_data and cn_data[key]:
                            total_skip += 1
                            continue
                        to_translate[key] = langs

                    if not to_translate:
                        self._log_translate(f"[跳过] {csv_name} - 全部已翻译")
                        continue

                    # 分批
                    items = list(to_translate.items())
                    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
                    file_total = len(items)
                    self._log_translate(f"[开始] {csv_name}: {file_total} 条待翻译，分 {len(batches)} 批×{batch_size}条，{threads}线程并发")

                    done_count = [0]
                    err_count = [0]
                    result_lock = threading.Lock()

                    file_start_time = time.time()

                    # 提交所有批次到线程池
                    futures = []
                    for batch_idx, batch in enumerate(batches):
                        future = executor.submit(
                            self._do_translate_batch,
                            ctx, csv_name, batch_idx, len(batches), batch,
                            done_count, err_count, result_lock, file_total,
                            global_done,
                        )
                        futures.append(future)

                    # 收集结果（基于时间间隔保存和刷新，减少I/O开销）
                    last_save_time = time.time()
                    last_refresh_time = time.time()
                    for future in as_completed(futures):
                        if self.translate_stop_event.is_set():
                            break
                        try:
                            future.result()
                        except Exception:
                            pass
                        # 更新进度条
                        _update_total_progress()
                        pct = done_count[0] / file_total * 100 if file_total else 100
                        self.root.after(0, lambda p=pct: self.translate_progress_var.set(p))
                        now = time.time()
                        # 每30秒自动保存一次CSV
                        if now - last_save_time >= 30:
                            self._auto_save_translations(csv_name)
                            last_save_time = now
                        # 每5秒刷新一次表格
                        if csv_name == self.current_file and now - last_refresh_time >= 5:
                            self.root.after(0, self._refresh_table)
                            last_refresh_time = now

                    # 文件翻译完成后保存并刷新
                    self._auto_save_translations(csv_name)
                    if csv_name == self.current_file:
                        self.root.after(0, self._refresh_table)
                    total_done += done_count[0]
                    total_err += err_count[0]
                    elapsed = time.time() - file_start_time
                    self._log_translate(f"[完成] {csv_name}: 成功 {done_count[0]}，失败 {err_count[0]}，耗时 {elapsed:.1f}s")
            finally:
                executor.shutdown(wait=False)

            self._log_translate(f"\n翻译结束！成功: {total_done}，跳过: {total_skip}，失败: {total_err}")
            self._log_translate(f"Token总计: 输入 {self.total_prompt_tokens:,} | 输出 {self.total_completion_tokens:,} | 合计 {self.total_tokens:,}")
            self.root.after(0, self._on_translate_done)

        threading.Thread(target=worker, daemon=True).start()

    def _get_or_create_thread_client(self, ctx):
        """获取当前线程的独立client（线程本地存储）"""
        tl = self._thread_local
        if not hasattr(tl, 'client'):
            tl.client = self._create_thread_client(ctx['client_config'])
        return tl.client

    def _do_translate_batch(self, ctx, csv_name, batch_idx, batch_total,
                            batch_items, done_count, err_count, result_lock, file_total,
                            global_done=None):
        """批量翻译：一次API调用翻译多条（每线程独立client）"""
        if self.translate_stop_event.is_set():
            return
        client = self._get_or_create_thread_client(ctx)
        model = ctx['model']
        temperature = ctx['temperature']
        sys_prompt = ctx['sys_prompt']
        tid = threading.current_thread().name

        # 构造批量JSON输入
        input_dict = {key: langs.get('en', '') for key, langs in batch_items}
        batch_json = json.dumps(input_dict, ensure_ascii=False)
        user_msg = (
            "请将以下JSON中的英文值翻译为中文，保持key不变，直接返回翻译后的JSON。"
            f"不要添加任何解释或markdown格式。\n{batch_json}"
        )

        for attempt in range(4):
            if self.translate_stop_event.is_set():
                return
            try:
                t0 = time.time()
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=temperature,
                    max_tokens=4096,
                )
                api_elapsed = time.time() - t0
                raw_content = resp.choices[0].message.content or ''
                # 统计token
                usage = getattr(resp, 'usage', None)
                p_tok = getattr(usage, 'prompt_tokens', 0) if usage else 0
                c_tok = getattr(usage, 'completion_tokens', 0) if usage else 0
                if usage:
                    self._update_token_stats(p_tok, c_tok)

                # 使用json_repair解析（比json.loads更健壮）
                result_dict = json_repair.loads(raw_content.strip())
                if not isinstance(result_dict, dict):
                    raise ValueError(f"LLM返回非dict类型: {type(result_dict)}")

                # key修正：LLM可能"纠正"key拼写，按顺序映射回原始key
                input_keys = list(input_dict.keys())
                returned_keys = list(result_dict.keys())
                unmatched = [k for k in returned_keys if k not in input_dict]
                if unmatched and len(returned_keys) == len(input_keys):
                    # 返回数量一致但key不同，按顺序映射
                    remapped = {}
                    for orig_k, ret_k in zip(input_keys, returned_keys):
                        remapped[orig_k] = result_dict[ret_k]
                    result_dict = remapped

                # 更新翻译结果（锁内只做dict更新，不做I/O）
                batch_done = 0
                with result_lock:
                    if csv_name not in self.translations:
                        self.translations[csv_name] = {}
                    for key, cn_val in result_dict.items():
                        if key in input_dict and cn_val and isinstance(cn_val, str):
                            # 去除原文换行，由patch_csv_bytes按用户设置重新换行
                            self.translations[csv_name][key] = cn_val.replace('\n', '').replace('\r', '').strip()
                            done_count[0] += 1
                            batch_done += 1
                            if global_done is not None:
                                global_done[0] += 1
                    pct = done_count[0] / file_total * 100
                    self.root.after(0, lambda p=pct: self.translate_progress_var.set(p))

                missing = [k for k, _ in batch_items if k not in result_dict]
                if missing:
                    with result_lock:
                        err_count[0] += len(missing)
                    # 诊断日志：显示期望key与实际返回key的差异
                    expected_keys = [k for k, _ in batch_items]
                    returned_keys = list(result_dict.keys())
                    self._log_translate(
                        f"    ⚠ 缺失{len(missing)}条 期望key: {expected_keys[:5]}... 返回key: {returned_keys[:5]}..."
                    )
                    if batch_done == 0:
                        self._log_translate(f"    ⚠ LLM原始返回(前200字): {raw_content[:200]}")

                self._log_translate(
                    f"  [{tid}][批{batch_idx+1}/{batch_total}] {batch_done}/{len(batch_items)}条OK  {api_elapsed:.1f}s (token:{p_tok}+{c_tok})"
                )
                return
            except Exception as e:
                err_str = str(e)
                is_rate = '429' in err_str or 'rate' in err_str.lower()
                if attempt == 3:
                    # 最终失败：回退逐条翻译
                    self._log_translate(f"  [批{batch_idx+1}] 批量失败，回退逐条: {err_str[:80]}")
                    for key, langs in batch_items:
                        if self.translate_stop_event.is_set():
                            return
                        self._do_translate_single(
                            ctx, csv_name, key, langs,
                            done_count, err_count, result_lock, file_total,
                            global_done,
                        )
                    return
                elif is_rate:
                    m = re.search(r'after\s+(\d+)\s*second', err_str)
                    wait = int(m.group(1)) + 1 if m else 5 * (attempt + 1)
                    self._log_translate(f"  [批{batch_idx+1}] 限频等待{wait}s...")
                    time.sleep(wait)
                else:
                    time.sleep(2 ** attempt)

    def _do_translate_single(self, ctx, csv_name, key, langs,
                             done_count, err_count, result_lock, file_total,
                             global_done=None):
        """单条翻译回退（每线程独立client）"""
        client = self._get_or_create_thread_client(ctx)
        model = ctx['model']
        en = langs.get('en', '')
        user_msg = f"KEY: {key}\nEnglish: {en}\n\n请翻译为中文（只输出翻译结果）："
        for attempt in range(3):
            if self.translate_stop_event.is_set():
                return
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": ctx['sys_prompt']},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=ctx['temperature'],
                    max_tokens=2048,
                )
                raw = resp.choices[0].message.content or ''
                result = raw.strip().strip('"').strip("'")
                for prefix in ['翻译：', '翻译:', '中文翻译：', '中文：', '中文:', '翻译结果：', '翻译结果:']:
                    if result.startswith(prefix):
                        result = result[len(prefix):].strip()
                usage = getattr(resp, 'usage', None)
                if usage:
                    self._update_token_stats(
                        getattr(usage, 'prompt_tokens', 0),
                        getattr(usage, 'completion_tokens', 0))
                if result.strip():
                    with result_lock:
                        if csv_name not in self.translations:
                            self.translations[csv_name] = {}
                        # 去除原文换行，由patch_csv_bytes按用户设置重新换行
                        self.translations[csv_name][key] = result.replace('\n', '').replace('\r', '').strip()
                        done_count[0] += 1
                        if global_done is not None:
                            global_done[0] += 1
                        pct = done_count[0] / file_total * 100
                        self.root.after(0, lambda p=pct: self.translate_progress_var.set(p))
                    return
            except Exception:
                time.sleep(2 ** attempt)
        with result_lock:
            err_count[0] += 1

    def _auto_save_translations(self, csv_name):
        """自动保存翻译结果到CSV（schinese列）"""
        csv_dir = self._get_csv_dir()
        csv_path = os.path.join(csv_dir, csv_name)
        if not os.path.isfile(csv_path):
            return
        trans = self.translations.get(csv_name, {})
        if not trans:
            return
        try:
            with open(csv_path, 'rb') as f:
                raw_bytes = f.read()
            # 保存时不换行，换行仅在打补丁时按用户设置处理
            patched_bytes, _ = patch_csv_bytes(raw_bytes, trans, CN_TARGET_LANG, wrap_width=None)
            tmp = csv_path + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(patched_bytes)
            os.replace(tmp, csv_path)
        except Exception:
            pass

    def _stop_translate(self):
        self.translate_stop_event.set()
        self._log_translate("[用户中断] 正在停止翻译...")

    def _on_translate_done(self):
        self.translate_running = False
        self.btn_start_translate.configure(state='normal')
        self.btn_stop_translate.configure(state='disabled')
        self.translate_progress_var.set(100)
        self.translate_pct_var.set("完成")
        self.translate_total_progress_var.set(100)
        self.translate_total_pct_var.set("完成")
        # 刷新文本管理页面
        self._on_gpak_loaded()

    # ==================== Tab3 打补丁 ====================

    def _fix_game_language(self):
        """修复游戏语言配置为官方语言，避免更新后报错"""
        game_dir = self.game_dir_var.get().strip()
        if not game_dir:
            messagebox.showwarning("提示", "请先设置游戏目录")
            return
        # 获取当前覆盖语言
        lang_file = os.path.join(game_dir, '.cn_patch_lang')
        old_lang = None
        if os.path.isfile(lang_file):
            with open(lang_file, 'r') as f:
                old_lang = f.read().strip()
        status, found = update_settings(game_dir, 'en')
        if status == 'updated':
            msg = f"已将游戏语言配置重置为 English"
            if old_lang:
                msg += f"\n（原设置: {old_lang}）"
            msg += "\n\n游戏更新后如果报语言错误，请先点此按钮修复，再重新应用补丁。"
            self._log_patch(msg)
            messagebox.showinfo("修复完成", msg)
        elif status == 'already':
            msg = "游戏语言配置已经是 English，无需修复"
            self._log_patch(msg)
            messagebox.showinfo("提示", msg)
        else:
            self._log_patch("未找到游戏设置文件，无法修复")
            messagebox.showwarning("提示", "未找到游戏设置文件（settings.txt）\n请确认游戏已运行过至少一次")

    def _browse_font(self):
        path = filedialog.askopenfilename(
            title="选择字体文件",
            filetypes=[("字体文件", "*.ttf *.otf"), ("所有文件", "*.*")]
        )
        if path:
            self.font_path_var.set(path)

    def _log_patch(self, msg):
        def _do():
            self.patch_log.configure(state='normal')
            self.patch_log.insert('end', msg + '\n')
            self.patch_log.see('end')
            self.patch_log.configure(state='disabled')
        self.root.after(0, _do)

    def _browse_csv_dir(self):
        path = filedialog.askdirectory(title="选择CSV文件目录")
        if path:
            self.csv_dir_var.set(path)
            self._refresh_patch_files()

    def _refresh_patch_files(self):
        """刷新补丁页的CSV文件列表（同时重新加载翻译数据）"""
        for w in self.patch_file_inner.winfo_children():
            w.destroy()
        self.patch_file_vars.clear()
        csv_dir = self.csv_dir_var.get().strip() if hasattr(self, 'csv_dir_var') else ''
        if not csv_dir or not os.path.isdir(csv_dir):
            ttk.Label(self.patch_file_inner, text="请先加载游戏数据或设置CSV目录", foreground='gray').pack(pady=5)
            return
        # 从CSV文件重新加载已有翻译
        self._load_translations_from_csvs(csv_dir)
        csv_files = sorted(f for f in os.listdir(csv_dir) if f.endswith('.csv'))
        if not csv_files:
            ttk.Label(self.patch_file_inner, text="CSV目录中没有CSV文件", foreground='gray').pack(pady=5)
            return
        col = 0
        row = 0
        max_rows = max(8, (len(csv_files) + 2) // 3)
        for fname in csv_files:
            cn_count = len(self.translations.get(fname, {}))
            total = self._count_translatable(fname) if fname in self.all_data else '?'
            label = f"{fname} ({cn_count}/{total})"
            var = tk.BooleanVar(value=True)
            self.patch_file_vars[fname] = var
            ttk.Checkbutton(self.patch_file_inner, text=label, variable=var).grid(row=row, column=col, sticky='w', padx=5)
            row += 1
            if row >= max_rows:
                row = 0
                col += 1

    def _set_all_patch(self, val):
        for v in self.patch_file_vars.values():
            v.set(val)

    def _apply_patch(self):
        """应用补丁：将选中的CSV文件替换进GPAK"""
        game_dir = self.game_dir_var.get().strip()
        if not game_dir or not os.path.isfile(os.path.join(game_dir, "resources.gpak")):
            messagebox.showerror("错误", "请先设置正确的游戏目录")
            return
        csv_dir = self.csv_dir_var.get().strip()
        if not csv_dir or not os.path.isdir(csv_dir):
            messagebox.showwarning("提示", "请先设置CSV目录（并导出/准备好CSV文件）")
            return
        # 使用用户勾选的文件
        csv_files = [f for f, var in self.patch_file_vars.items() if var.get()]
        if not csv_files:
            messagebox.showwarning("提示", "请至少勾选一个CSV文件")
            return

        font_path = self.font_path_var.get().strip()

        if not messagebox.askyesno("确认", f"将用 {len(csv_files)} 个CSV文件替换游戏数据。\n确定要应用补丁吗？"):
            return

        self._log_patch(f"开始应用补丁... ({len(csv_files)} 个CSV文件)")

        def worker():
            try:
                gpak_path = os.path.join(game_dir, "resources.gpak")

                # 读取GPAK索引
                self._log_patch("读取GPAK索引...")
                with open(gpak_path, 'rb') as fs:
                    entries, data_start = read_gpak_index(fs)
                self._log_patch(f"  文件总数: {len(entries)}")

                # 加载并处理用户选中的CSV文件（去除旧换行→按用户设置重新换行）
                self._log_patch("处理CSV文件（应用换行设置）...")
                wrap_chars = int(self.wrap_width_var.get()) if hasattr(self, 'wrap_width_var') else 15
                wrap_width = wrap_chars * 2 if wrap_chars > 0 else None
                self._log_patch(f"  换行字数: {wrap_chars}（{'不换行' if wrap_width is None else f'显示宽度{wrap_width}'}）")
                selected_set = set(csv_files)
                patch_files = {}
                for entry in entries:
                    name = entry['name']
                    if not name.startswith('data/text/') or not name.endswith('.csv'):
                        continue
                    csv_name = os.path.basename(name)
                    if csv_name not in selected_set:
                        continue
                    csv_path = os.path.join(csv_dir, csv_name)
                    if os.path.isfile(csv_path):
                        with open(csv_path, 'rb') as f:
                            raw_bytes = f.read()
                        # 获取该文件的翻译（去除换行的纯文本）
                        trans = self.translations.get(csv_name, {})
                        # 去除翻译中残留的换行
                        clean_trans = {}
                        for k, v in trans.items():
                            clean_trans[k] = v.replace('\n', '').replace('\r', '') if isinstance(v, str) else v
                        # 通过patch_csv_bytes重新写入schinese列（含自动换行）
                        patched_bytes, cnt = patch_csv_bytes(raw_bytes, clean_trans, CN_TARGET_LANG, wrap_width)
                        # 写回CSV文件
                        with open(csv_path, 'wb') as f:
                            f.write(patched_bytes)
                        patch_files[name] = patched_bytes
                        self._log_patch(f"  {csv_name} ({cnt}条翻译)")

                self._log_patch(f"  共替换 {len(patch_files)} 个CSV文件")

                # 字体替换
                if font_path and os.path.isfile(font_path):
                    self._log_patch(f"正在转换字体: {os.path.basename(font_path)}")
                    self._log_patch("（这可能需要1-3分钟，请耐心等待...）")
                    try:
                        from font_to_swf import convert_font_to_swf
                        orig_swf = extract_file_from_gpak(gpak_path, entries, data_start, 'swfs/unicodefont.swf')
                        if orig_swf:
                            new_swf = convert_font_to_swf(font_path, orig_swf, lambda msg: self._log_patch(f"  {msg}"))
                            patch_files['swfs/unicodefont.swf'] = new_swf
                            self._log_patch(f"  字体转换完成: {len(new_swf)/1024/1024:.1f} MB")
                        else:
                            self._log_patch("  [错误] 无法从GPAK提取原始字体")
                    except Exception as e:
                        self._log_patch(f"  [错误] 字体转换失败: {e}")
                        self._log_patch("  将继续使用默认字体")

                # 备份
                backup_path = gpak_path + '.bak'
                if not os.path.isfile(backup_path):
                    self._log_patch("备份原始GPAK...")
                    shutil.copy2(gpak_path, backup_path)
                    self._log_patch(f"  已备份: {backup_path}")

                # 写入新GPAK
                output_path = gpak_path + '.new'
                self._log_patch("正在写入补丁GPAK...")

                def progress_cb(done, total):
                    pct = done / total * 100
                    self.root.after(0, lambda: self.patch_progress_var.set(pct))

                write_gpak(output_path, entries, data_start, gpak_path, patch_files, progress_cb)

                # 替换
                os.replace(output_path, gpak_path)
                self._log_patch("GPAK已更新")

                # 更新语言设置为schinese
                s_status, _ = update_settings(game_dir, CN_TARGET_LANG)
                if s_status == 'not_found':
                    self._log_patch(f"⚠ 未找到游戏设置文件，请手动在游戏中切换语言为: {CN_TARGET_LANG}")
                else:
                    self._log_patch(f"游戏语言已设为: {CN_TARGET_LANG}")

                # 记录补丁语言
                try:
                    with open(os.path.join(game_dir, '.cn_patch_lang'), 'w') as f:
                        f.write(CN_TARGET_LANG)
                except Exception:
                    pass

                self._log_patch("\n✅ 补丁安装完成！启动游戏即可体验中文。")
                self.root.after(0, lambda: self.patch_progress_var.set(100))
                self.root.after(0, lambda: messagebox.showinfo("完成", "补丁安装成功！"))
            except Exception as e:
                err_msg = str(e)
                self._log_patch(f"\n[错误] {err_msg}")
                import traceback
                self._log_patch(traceback.format_exc())
                self.root.after(0, lambda m=err_msg: messagebox.showerror("错误", f"补丁安装失败:\n{m}"))

        threading.Thread(target=worker, daemon=True).start()

    def _restore_patch(self):
        """还原补丁"""
        game_dir = self.game_dir_var.get().strip()
        if not game_dir:
            messagebox.showerror("错误", "请先设置游戏目录")
            return
        backup_path = os.path.join(game_dir, "resources.gpak.bak")
        if not os.path.isfile(backup_path):
            messagebox.showwarning("提示", "未找到备份文件，无法还原")
            return
        if not messagebox.askyesno("确认", "确定要还原到原始状态吗？"):
            return

        try:
            gpak_path = os.path.join(game_dir, "resources.gpak")
            shutil.copy2(backup_path, gpak_path)
            self._log_patch("已从备份还原 resources.gpak")

            # 重置语言
            lang_file = os.path.join(game_dir, '.cn_patch_lang')
            if os.path.isfile(lang_file):
                with open(lang_file, 'r') as f:
                    old_lang = f.read().strip()
                update_settings(game_dir, 'en')
                os.remove(lang_file)
                self._log_patch(f"游戏语言已重置为英文（原覆盖: {old_lang}）")
            else:
                update_settings(game_dir, 'en')
                self._log_patch("游戏语言已重置为英文")

            self._log_patch("\n✅ 已还原到原始状态。")
            messagebox.showinfo("完成", "补丁已还原")
        except Exception as e:
            self._log_patch(f"[错误] {e}")
            messagebox.showerror("错误", f"还原失败: {e}")


# ==================== 入口 ====================

def main():
    root = tk.Tk()
    # 设置DPI感知（Windows高DPI适配）
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # 设置默认字体
    default_font = ('Microsoft YaHei UI', 9)
    root.option_add('*Font', default_font)

    style = ttk.Style()
    style.configure('Treeview', rowheight=24)

    app = TranslationToolApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
