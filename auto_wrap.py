#!/usr/bin/env python3
"""
自动给翻译JSON中的长中文文本插入换行符。
规则：
  - 每行显示宽度超过阈值时在合适位置插入\n
  - CJK字符宽度按2计算，ASCII按1
  - 不在标签[...]和占位符{...}内部断行
  - 优先在中文标点后断行
"""
import json
import os
import re

MAX_WIDTH = 40  # 最大行显示宽度

# 中文标点（适合在其后断行）
BREAK_AFTER = set('。！？；：，、）】」』》~')
# 不能出现在行首的标点（禁则处理）
NO_LINE_START = set('。！？；：，、）】」』》~.!?,;:)]}\'\"')

def display_width(text):
    """计算文本显示宽度（忽略格式标签）"""
    clean = re.sub(r'\[/?[^\]]*\]', '', text)
    clean = re.sub(r'\{[^\}]*\}', 'XX', clean)
    w = 0
    for c in clean:
        if ord(c) > 0x2E80:
            w += 2
        else:
            w += 1
    return w


def char_width(c):
    """单个字符的显示宽度"""
    if ord(c) > 0x2E80:
        return 2
    return 1


def is_inside_tag(text, pos):
    """检查位置是否在[...]或{...}标签内"""
    # 向前查找未闭合的[或{
    depth_sq = 0
    depth_br = 0
    for i in range(pos, -1, -1):
        if text[i] == ']':
            depth_sq += 1
        elif text[i] == '[':
            depth_sq -= 1
            if depth_sq < 0:
                return True
        elif text[i] == '}':
            depth_br += 1
        elif text[i] == '{':
            depth_br -= 1
            if depth_br < 0:
                return True
    return False


def wrap_line(text):
    """给单行文本插入换行符"""
    if display_width(text) <= MAX_WIDTH:
        return text

    result = []
    current_line = ''
    current_width = 0
    i = 0
    in_tag = False
    tag_char = ''

    while i < len(text):
        c = text[i]

        # 跟踪标签状态
        if not in_tag and (c == '[' or c == '{'):
            in_tag = True
            tag_char = ']' if c == '[' else '}'
        
        is_tag_end = (in_tag and c == tag_char)
        if is_tag_end:
            in_tag = False

        # 标签内容不计入显示宽度（[img:xxx]按2宽度）
        if in_tag or c in '[]{}':
            current_line += c
            if is_tag_end:
                tag_match = re.search(r'\[img:[^\]]*\]$', current_line)
                if tag_match:
                    current_width += 2
            i += 1
            continue

        cw = char_width(c)
        current_width += cw
        current_line += c
        i += 1

        # 检查是否需要换行
        if current_width >= MAX_WIDTH and not in_tag:
            best_break = _find_break_point(current_line)

            if best_break > 0:
                # 禁则处理：如果断点后紧跟不能出现在行首的标点，把标点一起带走
                while (best_break < len(current_line) and 
                       current_line[best_break] in NO_LINE_START):
                    best_break += 1
                
                # 如果带完标点后等于整行，就不断了
                if best_break >= len(current_line):
                    continue

                result.append(current_line[:best_break])
                remainder = current_line[best_break:]
                current_line = remainder
                current_width = display_width(remainder)

    if current_line:
        result.append(current_line)

    return '\n'.join(result)


def _find_break_point(line):
    """在行内查找最佳断行位置"""
    search_start = len(line) - 1
    min_pos = max(0, len(line) - 25)

    # 优先：在中文标点或空格后断行
    for j in range(search_start, min_pos, -1):
        ch = line[j]
        if ch in BREAK_AFTER and not is_inside_tag(line, j):
            return j + 1
        if ch == ' ' and not is_inside_tag(line, j):
            return j + 1

    # 次选：在CJK字符边界断行
    for j in range(search_start, min_pos, -1):
        if ord(line[j]) > 0x2E80 and line[j] not in NO_LINE_START and not is_inside_tag(line, j):
            return j + 1

    return -1


def wrap_text(text):
    """处理含有已有换行符的文本"""
    lines = text.split('\n')
    wrapped = [wrap_line(line) for line in lines]
    return '\n'.join(wrapped)


def process_file(filepath):
    """处理单个JSON翻译文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    modified = 0
    for key in data:
        original = data[key]
        wrapped = wrap_text(original)
        if wrapped != original:
            data[key] = wrapped
            modified += 1

    if modified > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return modified


def main():
    trans_dir = r'D:\Program Files (x86)\Steam\steamapps\common\Mewgenics\translations'
    total = 0
    for f in sorted(os.listdir(trans_dir)):
        if not f.endswith('.json') or f.endswith('_keys.json'):
            continue
        path = os.path.join(trans_dir, f)
        count = process_file(path)
        if count > 0:
            print(f'  {f}: {count} 条文本已换行')
            total += count
    print(f'共修改 {total} 条')


if __name__ == '__main__':
    main()
