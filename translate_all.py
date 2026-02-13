#!/usr/bin/env python3
"""
Mewgenics AI翻译工具
使用智谱AI API，结合多语言上下文，自动翻译游戏文本为中文。
"""
import struct
import json
import os
import sys
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

VERSION = "1.0"
BANNER = f"""
╔══════════════════════════════════════════╗
║   Mewgenics AI翻译工具 v{VERSION}             ║
║   使用智谱AI批量翻译游戏文本            ║
╚══════════════════════════════════════════╝
"""

# ============ 配置区 ============
# 智谱AI API密钥（留空则运行时提示输入）
API_KEY = ""
# 模型选择：glm-4-flash（免费快速）/ glm-4-plus（质量更高）
MODEL = "glm-4-flash"
# 并发线程数
THREADS = 10
# 每次API调用失败后的重试次数
MAX_RETRIES = 3
# API调用间隔（秒，防止限速）
API_DELAY = 0.1

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

# 翻译风格分类
NARRATIVE_FILES = {"npc_dialog.csv", "events.csv", "cutscene_text.csv", "progression.csv"}
SKIP_FILES = {"pronouns.csv"}  # 代词不需要AI翻译

# 核心术语表（system prompt中使用）
GLOSSARY = """
## 核心术语表（翻译时必须统一使用）
| English | 中文 |
|---------|------|
| Shield | 护盾 |
| Thorns | 荆棘 |
| Brace | 硬抗 |
| Bleed | 流血 |
| Burn | 灼烧 |
| Poison | 中毒 |
| Blind | 致盲 |
| Freeze | 冻结 |
| Stun | 眩晕 |
| Fear | 恐惧 |
| Madness | 狂暴 |
| Confusion | 混乱 |
| Charmed | 魅惑 |
| Immobile | 定身 |
| Knockback | 击退 |
| Dodge | 闪避 |
| Lifesteal | 吸血 |
| Health Regen | 生命恢复 |
| Mana Regen | 法力恢复 |
| Charge | 蓄能 |
| Bruise | 淤伤 |
| Cleave | 劈砍 |
| Petrify | 石化 |
| Doomed | 末日 |
| Hex | 咒术 |
| Stealth | 潜行 |
| Exhaustion | 疲劳 |
| Constitution | 体质 |
| Intelligence | 智力 |
| Dexterity | 敏捷 |
| Charisma | 魅力 |
| Luck | 幸运 |
| Strength | 力量 |
| Kinetic Spikes | 动能尖刺 |
| Holy Shield | 神圣护盾 |
| Sparkle | 火花 |
| Familiar | 使魔 |
| Champion | 勇者 |
| Elite | 精英 |
| Alpha | 头领 |
| Bounty | 悬赏 |
| Backflip | 后空翻 |
| Counter Attack | 反击 |
| Double Cast | 双重施法 |
| Reflect | 反射 |
| Rot | 腐烂 |
| Leeches | 水蛭 |
| Meaty | 多肉的 |
| Ostracized | 被排斥 |
| Possessed | 附身 |
| Mutation | 变异 |
| Passive | 被动 |
| Ability | 技能 |
| Spell | 法术 |
| Basic Attack | 基础攻击 |
| Ranged | 远程 |
| Melee | 近战 |
| Tile | 格 |
| Round | 回合 |
| Turn | 回合 |
| Downed | 倒下 |
| Corpse | 尸体 |
| Pickup | 拾取物 |
| Consumable | 消耗品 |
| Trinket | 饰品 |
| Collar | 项圈 |
| Buff | 增益 |
| Debuff | 减益 |
| Crit/Critical Hit | 暴击 |
| Miss | 未命中 |
| Stack | 层 |
| Cat/Cats | 猫咪 |
| Kitten | 小猫 |
| Maggot | 蛆虫 |
| Flea | 跳蚤 |
| Fly/Flies | 苍蝇 |
"""

# ============ system prompt ============
SYSTEM_PROMPT_MECHANICAL = f"""你是一个专业的游戏本地化翻译专家，正在翻译一款名为Mewgenics的猫咪战术肉鸽游戏。

## 游戏背景
Mewgenics是由Edmund McMillen（以撒的结合作者）开发的回合制战术猫咪繁殖roguelite游戏。
玩家繁殖猫咪、装备职业项圈、派它们去冒险战斗。游戏风格黑色幽默，有血腥、粗俗元素。

## 翻译要求
1. 简洁准确，优先传达游戏机制含义
2. 语言自然流畅，避免机翻味和翻译腔
3. 不要用"吃伤"、"吃到伤害"等不常见说法，用"受到伤害"
4. 不要过度意译，保持信息完整
5. **必须保留所有格式标签**：[img:xxx]、[b]...[/b]、[s:数字]...[/s]、[i]...[/i]、[a:xxx]...[/a] 等
6. **必须保留所有占位符**：{{stacks}}、{{absstacks}}、{{catname}}、{{Catname}}、{{he}}、{{He}}、{{his}}、{{him}}、{{applier}}、{{applier's}} 等花括号内容原样保留
7. 只输出翻译结果，不要输出解释

{GLOSSARY}"""

SYSTEM_PROMPT_NARRATIVE = f"""你是一个专业的游戏本地化翻译专家，正在翻译一款名为Mewgenics的猫咪战术肉鸽游戏。

## 游戏背景
Mewgenics是由Edmund McMillen（以撒的结合作者）开发的回合制战术猫咪繁殖roguelite游戏。
玩家繁殖猫咪、装备职业项圈、派它们去冒险战斗。游戏风格黑色幽默，有血腥、粗俗、荒诞元素。
NPC性格鲜明，对话风格幽默。Thomas A. Beanies是疯狂科学家，Tracy是愤世嫉俗的宠物店员。

## 翻译要求
1. 翻译要有人味，诙谐自然，符合角色性格
2. 适当融入中文互联网的表达习惯，但不要生硬加梗
3. 英文俚语/俗语要意译为对应的中文表达，不要直译（如"elbow grease"="苦功夫"，不是"肘部油脂"）
4. 保持原文的情感和语气（幽默、讽刺、恐惧、悲伤等）
5. **必须保留所有格式标签**：[m:xxx]表情标签、[b]...[/b]、[s:数字]...[/s]、[i]...[/i]、[a:xxx]...[/a] 等
6. **必须保留所有占位符**：{{catname}}、{{Catname}}、{{he}}、{{He}}、{{his}}、{{him}}、{{Catname's}} 等花括号内容原样保留
7. 保留原文的换行(\n)位置，不要随意增删换行
8. 只输出翻译结果，不要输出解释

{GLOSSARY}"""


# ============ GPAK读取 ============
def read_gpak_index(fs):
    """读取GPAK文件索引"""
    count = struct.unpack('<I', fs.read(4))[0]
    entries = []
    for _ in range(count):
        name_len = struct.unpack('<H', fs.read(2))[0]
        name = fs.read(name_len).decode('utf-8')
        size = struct.unpack('<I', fs.read(4))[0]
        entries.append({'name': name, 'size': size})
    data_start = fs.tell()
    return entries, data_start


def extract_file_from_gpak(gpak_path, entries, data_start, target_name):
    """从GPAK中提取指定文件"""
    offset = data_start
    with open(gpak_path, 'rb') as fs:
        for entry in entries:
            if entry['name'] == target_name:
                fs.seek(offset)
                return fs.read(entry['size'])
            offset += entry['size']
    return None


def split_csv_fields(row_text):
    """将CSV行拆分为字段列表"""
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
    """将CSV文本分割为逻辑行"""
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


def extract_all_languages(gpak_path):
    """从GPAK提取所有CSV的所有语言列，返回 {csv_name: {KEY: {lang: text}}}"""
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

        # 解析header获取所有语言列
        header = rows[0].rstrip('\r\n')
        header_fields = split_csv_fields(header)
        lang_cols = {}  # {col_idx: lang_name}
        skip_cols = {'notes'}
        for idx, f in enumerate(header_fields):
            col_name = f.strip().lower()
            if idx == 0 or col_name in skip_cols or not col_name:
                continue
            lang_cols[idx] = col_name

        # 解析数据行
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


# ============ 智谱AI调用 ============
_api_lock = threading.Lock()
_call_count = 0
_error_count = 0
_skip_count = 0


def call_zhipu_api(client, model, system_prompt, user_message, max_retries=MAX_RETRIES):
    """调用智谱AI API，含重试逻辑"""
    global _call_count, _error_count
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            result = response.choices[0].message.content.strip()
            with _api_lock:
                _call_count += 1
            return result
        except Exception as e:
            err_msg = str(e)
            if attempt < max_retries - 1:
                # 限速则等待
                wait = 2 ** (attempt + 1)
                if '429' in err_msg or 'rate' in err_msg.lower():
                    wait = 5 * (attempt + 1)
                time.sleep(wait)
            else:
                with _api_lock:
                    _error_count += 1
                return None


def build_user_message(key, lang_data):
    """构造翻译请求的用户消息"""
    parts = [f"KEY: {key}"]
    # 语言优先级：英文最重要
    lang_order = ['en', 'sp', 'fr', 'de', 'it', 'pt-br']
    lang_names = {
        'en': 'English',
        'sp': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt-br': 'Portuguese',
    }
    for lang in lang_order:
        if lang in lang_data:
            parts.append(f"{lang_names.get(lang, lang)}: {lang_data[lang]}")

    parts.append("\n请将以上内容翻译为中文（只输出中文翻译结果）：")
    return '\n'.join(parts)


# ============ 翻译处理 ============
def translate_file(client, csv_name, csv_data, output_dir, model):
    """翻译单个CSV文件的所有条目"""
    global _skip_count
    json_name = CSV_TO_JSON.get(csv_name)
    if not json_name:
        return

    if csv_name in SKIP_FILES:
        print(f"  [跳过] {csv_name}（不需要AI翻译）")
        return

    output_path = os.path.join(output_dir, json_name)

    # 加载已有翻译（断点续传）
    existing = {}
    if os.path.isfile(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            pass

    # 筛选需要翻译的条目
    to_translate = {}
    for key, lang_data in csv_data.items():
        # 跳过空英文、已翻译的、空值后缀条目
        en_text = lang_data.get('en', '')
        if not en_text:
            continue
        if key in existing and existing[key]:
            with _api_lock:
                _skip_count += 1
            continue
        to_translate[key] = lang_data

    if not to_translate:
        print(f"  [已完成] {json_name}（{len(existing)} 条已有翻译）")
        return

    print(f"  [翻译中] {json_name}：{len(to_translate)} 条待翻译，{len(existing)} 条已有")

    # 选择system prompt
    is_narrative = csv_name in NARRATIVE_FILES
    system_prompt = SYSTEM_PROMPT_NARRATIVE if is_narrative else SYSTEM_PROMPT_MECHANICAL

    # 用于线程安全地更新翻译结果
    result_lock = threading.Lock()
    results = dict(existing)
    completed = [0]
    total = len(to_translate)

    def translate_one(key, lang_data):
        user_msg = build_user_message(key, lang_data)
        if API_DELAY > 0:
            time.sleep(API_DELAY)
        translation = call_zhipu_api(client, model, system_prompt, user_msg)
        if translation:
            # 清理AI可能添加的引号或多余内容
            translation = translation.strip().strip('"').strip("'")
            # 移除AI可能添加的"翻译："前缀
            for prefix in ['翻译：', '翻译:', '中文翻译：', '中文翻译:', '中文：', '中文:']:
                if translation.startswith(prefix):
                    translation = translation[len(prefix):].strip()
            with result_lock:
                results[key] = translation
                completed[0] += 1
                if completed[0] % 50 == 0 or completed[0] == total:
                    print(f"    {json_name}: {completed[0]}/{total}")
                    # 定期保存
                    _save_json(output_path, results)

    # 多线程翻译
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {
            executor.submit(translate_one, key, lang_data): key
            for key, lang_data in to_translate.items()
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                key = futures[future]
                print(f"    [错误] {key}: {e}")

    # 最终保存
    _save_json(output_path, results)
    print(f"  [完成] {json_name}：共 {len(results)} 条翻译")


def _save_json(path, data):
    """安全写入JSON文件"""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ============ 游戏目录查找 ============
def find_game_dir():
    """查找游戏目录"""
    candidates = [os.getcwd()]
    if getattr(sys, 'frozen', False):
        candidates.insert(0, os.path.dirname(sys.executable))
    candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for drive in 'CDEF':
        candidates.append(rf"{drive}:\Program Files (x86)\Steam\steamapps\common\Mewgenics")
        candidates.append(rf"{drive}:\SteamLibrary\steamapps\common\Mewgenics")
    for path in candidates:
        if os.path.isfile(os.path.join(path, "resources.gpak")):
            return path
    return None


# ============ 主流程 ============
def main():
    global THREADS
    print(BANNER)

    # API密钥
    api_key = API_KEY
    if not api_key:
        api_key = os.environ.get('ZHIPUAI_API_KEY', '')
    if not api_key:
        print("请输入智谱AI API密钥（在 https://open.bigmodel.cn 获取）：")
        api_key = input("> ").strip()
    if not api_key:
        print("[错误] 未提供API密钥")
        input("按回车键退出...")
        return 1

    # 初始化客户端
    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=api_key)
    except ImportError:
        print("[错误] 未安装zhipuai库，请运行: pip install zhipuai")
        input("按回车键退出...")
        return 1

    # 模型选择
    print(f"\n当前模型: {MODEL}")
    print("可选模型：")
    print("  1. glm-4-flash （免费，速度快，适合大批量）")
    print("  2. glm-4-plus  （收费，质量更高，适合精翻）")
    print("  3. glm-4-long  （收费，长文本，适合对话翻译）")
    model_choice = input("选择模型 [1-3]，默认1: ").strip()
    model_map = {'1': 'glm-4-flash', '2': 'glm-4-plus', '3': 'glm-4-long'}
    model = model_map.get(model_choice, MODEL)
    print(f"  使用模型: {model}")

    # 线程数
    print(f"\n并发线程数: {THREADS}")
    thread_input = input(f"输入线程数（默认{THREADS}）: ").strip()
    if thread_input.isdigit() and int(thread_input) > 0:
        THREADS = int(thread_input)
    print(f"  线程数: {THREADS}")

    # 查找游戏目录
    print("\n正在查找游戏目录...")
    game_dir = find_game_dir()
    if not game_dir:
        game_dir = input("请输入Mewgenics游戏目录路径: ").strip().strip('"')
    gpak_path = os.path.join(game_dir, "resources.gpak")
    # 优先使用备份（原始未打补丁的GPAK）
    bak_path = gpak_path + '.bak'
    if os.path.isfile(bak_path):
        gpak_path = bak_path
        print(f"  使用原始备份: {gpak_path}")
    elif os.path.isfile(gpak_path):
        print(f"  GPAK文件: {gpak_path}")
    else:
        print(f"[错误] 未找到 resources.gpak")
        input("按回车键退出...")
        return 1

    # 输出目录
    output_dir = os.path.join(game_dir, 'translations')
    os.makedirs(output_dir, exist_ok=True)
    print(f"  翻译输出: {output_dir}")

    # 提取所有语言
    print("\n正在从GPAK提取多语言文本...")
    all_data, entries, data_start = extract_all_languages(gpak_path)
    total_keys = sum(len(v) for v in all_data.values())
    print(f"  共提取 {len(all_data)} 个CSV，{total_keys} 条文本")

    # 验证API连接
    print("\n正在验证API连接...")
    try:
        test_resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "你好，请回复OK"}],
            max_tokens=10,
        )
        print(f"  API连接成功: {test_resp.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"  [错误] API连接失败: {e}")
        input("按回车键退出...")
        return 1

    # 选择要翻译的文件
    print("\n可翻译的文件：")
    csv_names = sorted(all_data.keys())
    for i, name in enumerate(csv_names):
        count = len(all_data[name])
        json_name = CSV_TO_JSON.get(name, '?')
        marker = " [跳过]" if name in SKIP_FILES else ""
        print(f"  {i+1:2d}. {json_name:<30s} ({count} 条){marker}")
    print(f"  0. 全部翻译")
    print()
    file_choice = input("选择要翻译的文件编号（多个用逗号分隔，默认0全部）: ").strip()
    if file_choice == '' or file_choice == '0':
        selected = csv_names
    else:
        indices = [int(x.strip()) - 1 for x in file_choice.split(',') if x.strip().isdigit()]
        selected = [csv_names[i] for i in indices if 0 <= i < len(csv_names)]

    # 开始翻译
    print(f"\n{'='*44}")
    print(f"  开始翻译 {len(selected)} 个文件")
    print(f"  模型: {model} | 线程: {THREADS}")
    print(f"{'='*44}\n")

    start_time = time.time()

    for csv_name in selected:
        if csv_name in all_data:
            translate_file(client, csv_name, all_data[csv_name], output_dir, model)

    elapsed = time.time() - start_time
    print(f"\n{'='*44}")
    print(f"  翻译完成！")
    print(f"  API调用: {_call_count} 次")
    print(f"  跳过已有: {_skip_count} 条")
    print(f"  失败: {_error_count} 次")
    print(f"  耗时: {elapsed:.1f} 秒")
    print(f"  翻译文件保存在: {output_dir}")
    print(f"{'='*44}")
    print()
    input("按回车键退出...")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已取消。已完成的翻译已保存。")
        sys.exit(0)
    except Exception as e:
        print(f"\n[致命错误] {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
        sys.exit(1)
