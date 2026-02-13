#!/usr/bin/env python3
"""
恢复被auto_wrap错误修改的JSON翻译文件。
策略：
  - 有_keys.json的文件：用英文\n数量确定原始结构，合并最小宽度边界
  - 无_keys.json的文件：合并连续短段（合并后宽度<=50的视为auto_wrap拆分）
"""
import json
import os
import re

TRANS_DIR = r'D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\translations'
MERGE_THRESHOLD = 50  # 无_keys时，合并后宽度<=此值的视为需要合并


def display_width(text):
    """计算文本显示宽度"""
    clean = re.sub(r'\[/?[^\]]*\]', '', text)
    clean = re.sub(r'\{[^\}]*\}', 'XX', clean)
    w = 0
    for c in clean:
        if ord(c) > 0x2E80:
            w += 2
        else:
            w += 1
    return w


def restore_with_keys(zh_text, en_text):
    """用英文\n数量恢复中文原始换行结构"""
    target_nl = en_text.count('\n')
    zh_parts = zh_text.split('\n')
    current_nl = len(zh_parts) - 1

    if current_nl <= target_nl:
        return zh_text

    # 反复合并最小宽度边界，直到\n数量匹配
    while len(zh_parts) - 1 > target_nl:
        best_idx = 0
        best_width = float('inf')
        for i in range(len(zh_parts) - 1):
            merged_w = display_width(zh_parts[i] + zh_parts[i + 1])
            if merged_w < best_width:
                best_width = merged_w
                best_idx = i
        zh_parts = zh_parts[:best_idx] + [zh_parts[best_idx] + zh_parts[best_idx + 1]] + zh_parts[best_idx + 2:]

    return '\n'.join(zh_parts)


def restore_without_keys(zh_text):
    """无英文对照时，合并连续短段恢复原始结构"""
    zh_parts = zh_text.split('\n')
    if len(zh_parts) <= 1:
        return zh_text

    # 合并连续段：如果合并后宽度<=阈值，则合并
    merged = [zh_parts[0]]
    for i in range(1, len(zh_parts)):
        combined = merged[-1] + zh_parts[i]
        if display_width(combined) <= MERGE_THRESHOLD:
            merged[-1] = combined
        else:
            merged.append(zh_parts[i])

    return '\n'.join(merged)


def process_file(zh_path, keys_path=None):
    """处理单个翻译文件"""
    with open(zh_path, 'r', encoding='utf-8') as f:
        zh_data = json.load(f)

    en_data = None
    if keys_path and os.path.exists(keys_path):
        with open(keys_path, 'r', encoding='utf-8') as f:
            en_data = json.load(f)

    modified = 0
    for key in zh_data:
        original = zh_data[key]
        if '\n' not in original:
            continue

        if en_data and key in en_data:
            restored = restore_with_keys(original, en_data[key])
        else:
            restored = restore_without_keys(original)

        if restored != original:
            zh_data[key] = restored
            modified += 1

    if modified > 0:
        with open(zh_path, 'w', encoding='utf-8') as f:
            json.dump(zh_data, f, ensure_ascii=False, indent=2)

    return modified


def main():
    total = 0
    for f in sorted(os.listdir(TRANS_DIR)):
        if not f.endswith('.json') or f.endswith('_keys.json'):
            continue
        zh_path = os.path.join(TRANS_DIR, f)
        keys_f = f.replace('.json', '_keys.json')
        keys_path = os.path.join(TRANS_DIR, keys_f)
        has_keys = os.path.exists(keys_path)

        count = process_file(zh_path, keys_path if has_keys else None)
        if count > 0:
            method = "keys对照" if has_keys else "宽度启发"
            print(f'  {f}: 恢复 {count} 条 ({method})')
            total += count
    print(f'共恢复 {total} 条')


if __name__ == '__main__':
    main()
