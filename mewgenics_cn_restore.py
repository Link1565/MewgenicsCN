#!/usr/bin/env python3
"""
Mewgenics 中文补丁 - 恢复工具
将游戏还原为未打补丁的状态，同时重置语言设置
"""
import os
import sys
import re

def find_game_dir():
    """查找游戏目录（优先找.bak，其次找.gpak）"""
    candidates = [
        os.getcwd(),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
        r"D:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
        r"E:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
        r"D:\SteamLibrary\steamapps\common\Mewgenics",
        r"E:\SteamLibrary\steamapps\common\Mewgenics",
    ]
    if getattr(sys, 'frozen', False):
        candidates.insert(0, os.path.dirname(sys.executable))
    # 优先找有备份的目录
    for path in candidates:
        if os.path.isfile(os.path.join(path, "resources.gpak.bak")):
            return path
    # 其次找有gpak的目录（仅重置语言用）
    for path in candidates:
        if os.path.isfile(os.path.join(path, "resources.gpak")):
            return path
    return None

def get_patched_lang(game_dir):
    """读取补丁记录的覆盖语言"""
    # 可能覆盖的语言列表
    possible = ['pt-br', 'it', 'de', 'fr', 'sp', 'schinese']
    if game_dir:
        record = os.path.join(game_dir, '.cn_patch_lang')
        if os.path.isfile(record):
            with open(record, 'r') as f:
                lang = f.read().strip()
            if lang:
                return [lang]
    return possible

def reset_language(game_dir):
    """将游戏语言设置重置为英文"""
    langs = get_patched_lang(game_dir)
    appdata = os.environ.get('APPDATA', '')
    settings_base = os.path.join(appdata, 'Glaiel Games', 'Mewgenics')
    if not os.path.isdir(settings_base):
        print("  未找到游戏设置目录")
        return
    # 构建匹配所有可能语言的正则
    pattern = r'current_language\s+(' + '|'.join(re.escape(l) for l in langs) + ')'
    for steam_dir in os.listdir(settings_base):
        settings_path = os.path.join(settings_base, steam_dir, 'settings.txt')
        if os.path.isfile(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            new_content = re.sub(pattern, 'current_language en', content)
            if new_content != content:
                with open(settings_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"  [已重置] 语言设置恢复为英文: {settings_path}")
            else:
                print(f"  [已是英文] {settings_path}")
    # 清理语言记录文件
    if game_dir:
        record = os.path.join(game_dir, '.cn_patch_lang')
        if os.path.isfile(record):
            try:
                os.remove(record)
            except Exception:
                pass

def main():
    print("Mewgenics 中文补丁 - 恢复工具")
    print("=" * 40)

    game_dir = find_game_dir()
    if not game_dir:
        game_dir = input("请输入游戏目录路径: ").strip().strip('"')

    bak = os.path.join(game_dir, "resources.gpak.bak") if game_dir else None
    gpak = os.path.join(game_dir, "resources.gpak") if game_dir else None

    if bak and os.path.isfile(bak):
        print(f"备份文件: {bak}")
        print(f"目标文件: {gpak}")
        confirm = input("确认恢复原始版本？(y/n): ").strip().lower()
        if confirm == 'y':
            try:
                os.replace(bak, gpak)
                print("[成功] 已恢复原始 resources.gpak")
            except Exception as e:
                print(f"[错误] {e}")
                input("按回车键退出...")
                return 1
    else:
        print("[提示] 未找到备份文件，跳过GPAK恢复。")

    # 重置语言设置为英文
    print()
    print("正在重置语言设置...")
    reset_language(game_dir)

    print()
    print("完成！")
    input("按回车键退出...")
    return 0

if __name__ == '__main__':
    sys.exit(main())
