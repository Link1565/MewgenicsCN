# Mewgenics 游戏汉化工具箱 v1.0

一款为 **Mewgenics**（喵喵的结合）游戏打造的一站式中文汉化工具，集成文本提取、AI翻译、手动编辑、补丁打包等全部功能。

> Mewgenics 是由 Edmund McMillen（《以撒的结合》《超级肉肉哥》作者）和 Tyler Glaiel 开发的回合制猫咪战术肉鸽游戏。

---

## 功能特性

- **一键读取游戏文本** — 自动从游戏 `resources.gpak` 文件中提取所有多语言 CSV 数据
- **多供应商 AI 翻译** — 支持智谱AI、DeepSeek、通义千问、Moonshot/Kimi、硅基流动、OpenAI 及自定义 OpenAI 兼容 API
- **多线程并发翻译** — 可配置并发线程数和批量大小，大幅提高翻译速度
- **手动编辑翻译** — 表格式翻译管理，支持搜索、筛选未翻译条目、双击编辑
- **智能换行** — 打补丁时按用户设置的字数自动换行，适配游戏内显示
- **自定义字体替换** — 支持将 TTF/OTF 字体转换为游戏 SWF 格式并替换
- **选择性打补丁** — 可勾选要替换的 CSV 文件，灵活控制补丁范围
- **一键还原** — 自动备份原始文件，随时还原到未打补丁的状态
- **游戏语言配置修复** — 自动处理游戏 `settings.txt` 中的语言设置
- **翻译自动保存** — AI 翻译结果实时保存到 CSV 文件，防止丢失

---

## 环境要求

- **Python 3.8+**（推荐 3.11）
- 依赖包：
  ```
  openai
  json_repair
  httpx
  fonttools  （仅替换字体时需要）
  ```

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/你的用户名/MewgenicsCN.git
cd MewgenicsCN
```

### 2. 安装依赖

```bash
pip install openai json_repair httpx fonttools
```

### 3. 运行工具

```bash
python translation_tool.py
```

工具会自动在 Steam 常用安装路径中查找 Mewgenics 游戏目录。如果未找到，请手动在界面顶部设置游戏目录路径。

---

## 使用教程

工具界面分为三个标签页：**文本管理**、**AI翻译**、**打补丁**。

### 第一步：文本管理

1. 确认顶部的**游戏目录**路径正确（应包含 `resources.gpak` 文件）
2. 点击 **「从游戏读取文本」** 按钮
3. 等待加载完成，文件下拉框会显示所有 CSV 文件及其翻译进度
4. 选择文件即可查看/编辑翻译内容

**功能说明：**

| 功能 | 说明 |
|------|------|
| 搜索 | 在 KEY、英文、中文列中模糊搜索 |
| 只显示未翻译 | 勾选后仅显示尚未翻译的条目 |
| 双击编辑 | 双击表格行可在底部编辑区修改中文翻译 |
| 保存 | 点击保存按钮会立即写入 CSV 文件 |

### 第二步：AI翻译

1. 切换到 **「AI翻译」** 标签页
2. 配置 AI 供应商：
   - 从下拉框选择供应商（或选"自定义"填入 OpenAI 兼容 API 地址）
   - 输入 **API 密钥**
   - 选择或手动输入**模型名称**（可点击"获取模型列表"自动拉取）
3. 调整翻译参数：

   | 参数 | 说明 | 建议值 |
   |------|------|--------|
   | 温度 (temperature) | 控制翻译的创造性，越高越多样 | 0.3~0.7 |
   | 并发线程 | 同时发出的 API 请求数 | 3~10 |
   | 批量大小 | 每次 API 请求翻译的条目数 | 10 |
   | 翻译模式 | "添加"跳过已翻译条目，"覆盖"重翻所有 | 添加 |

4. 可编辑**翻译提示词**（System Prompt），工具内置了针对 Mewgenics 游戏风格的详细提示词和术语表
5. 勾选要翻译的**文件**
6. 点击 **「开始翻译」**

**翻译过程中：**
- 进度条显示当前文件和总体进度
- 日志区实时显示每批次的耗时、Token 用量
- 翻译结果自动保存到 CSV 文件
- 可随时点击"停止"中断翻译

### 第三步：打补丁

1. 切换到 **「打补丁」** 标签页
2. 确认 **CSV 目录**正确（默认为游戏目录下的 `csv_export`）
3. 设置**游戏内换行字数**（推荐 15，设为 0 则不换行）
4. （可选）选择**字体文件**（.ttf/.otf），留空则使用游戏默认字体
5. 在文件列表中**勾选**要替换的 CSV 文件
6. 点击 **「🔧 应用补丁（CSV→游戏）」**

**补丁流程：**
1. 读取 GPAK 索引
2. 对每个勾选的 CSV 文件：去除旧换行 → 按设定字数重新换行 → 写入 schinese 列 → 写回 CSV
3. 如有自定义字体，转换为游戏 SWF 格式
4. 备份原始 `resources.gpak` 为 `resources.gpak.bak`
5. 生成新 GPAK 并替换
6. 自动将游戏语言设置为 `schinese`

---

## 还原补丁

有三种方式还原到原版：

1. **工具内还原** — 在"打补丁"标签页点击 **「🔄 还原补丁」**
2. **手动还原** — 将游戏目录下的 `resources.gpak.bak` 重命名为 `resources.gpak`
3. **Steam 验证** — 在 Steam 中右键游戏 → 属性 → 本地文件 → 验证游戏文件完整性

---

## 打包为 EXE

如需分发给不会安装 Python 的用户：

```bash
pip install pyinstaller
# Windows
pyinstaller --onefile --name "游戏汉化工具箱" translation_tool.py
```

或直接运行项目中的 `build_exe.bat`（会同时打包补丁工具和恢复工具）。

打包后的文件在 `dist/` 目录中。

---

## 翻译文件说明

游戏的翻译内容分布在以下 CSV 文件中：

| 文件 | 说明 | 大致条数 |
|------|------|----------|
| abilities.csv | 猫咪技能名称与描述 | ~2000 |
| additions.csv | 附加文本（含语言配置） | ~100 |
| additions2.csv | 附加文本 2 | ~80 |
| additions3.csv | 附加文本 3 | ~30 |
| cutscene_text.csv | 过场动画文本 | ~200 |
| enemy_abilities.csv | 敌人技能 | ~50 |
| events.csv | 随机事件文本 | ~2500 |
| furniture.csv | 家具描述 | ~50 |
| items.csv | 物品名称与描述 | ~1000 |
| keyword_tooltips.csv | 关键词工具提示 | ~200 |
| misc.csv | 杂项界面文本 | ~100 |
| mutations.csv | 变异描述 | ~150 |
| npc_dialog.csv | NPC 对话 | ~2500 |
| passives.csv | 被动技能描述 | ~800 |
| progression.csv | 进度/解锁文本 | ~150 |
| pronouns.csv | 代词 | ~20 |
| teamnames.csv | 队伍名称 | ~50 |
| units.csv | 单位/猫咪描述 | ~400 |
| weather.csv | 天气描述 | ~60 |

---

## 项目结构

```
MewgenicsCN/
├── translation_tool.py      # 主程序（GUI 汉化工具箱）
├── font_to_swf.py           # 字体转换模块（TTF/OTF → SWF）
├── mewgenics_cn_patch.py    # 命令行补丁工具（独立使用）
├── mewgenics_cn_restore.py  # 命令行还原工具
├── translate_all.py         # 命令行批量翻译脚本
├── build_exe.bat            # PyInstaller 打包脚本
├── 游戏汉化工具箱.spec       # PyInstaller 配置
└── README.md
```

---

## 支持的 AI 供应商

| 供应商 | API 地址 | 推荐模型 |
|--------|---------|----------|
| 智谱AI (Zhipu) | `https://open.bigmodel.cn/api/paas/v4` | glm-4-flash（免费） |
| DeepSeek | `https://api.deepseek.com` | deepseek-chat |
| 通义千问 (Qwen) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-plus |
| Moonshot/Kimi | `https://api.moonshot.cn/v1` | moonshot-v1-8k |
| 硅基流动 (SiliconFlow) | `https://api.siliconflow.cn/v1` | 按需选择 |
| OpenAI | `https://api.openai.com/v1` | gpt-4o-mini |
| 自定义 | 任意 OpenAI 兼容 API | — |

> 所有供应商均使用 OpenAI 兼容接口，理论上任何兼容 `/v1/chat/completions` 的 API 都可以使用。

---

## 常见问题

### Q: 游戏语言选项显示 "???"
A: 在"打补丁"标签页点击 **「🛠 修复游戏语言配置」**，或重新应用补丁。这通常是因为 `additions.csv` 中的 `CURRENT_LANGUAGE_SHIPPABLE` 值不正确。

### Q: 游戏更新后补丁失效了
A: 重新运行工具，点击"从游戏读取文本"→ 切到"打补丁"→ 重新应用补丁即可。你之前的翻译保存在 `csv_export` 目录中不会丢失。

### Q: 翻译结果中有乱码或格式错误
A: 检查翻译提示词中是否保留了格式标签规则。可以在"文本管理"中双击编辑有问题的条目并手动修正。

### Q: 如何只翻译特定文件？
A: 在"AI翻译"标签页中取消勾选不需要翻译的文件。在"打补丁"标签页中也可以只勾选需要打补丁的文件。

### Q: 字体替换后部分字显示为方块
A: 所选字体可能不包含某些中文字符。推荐使用覆盖面较广的字体（如思源黑体、文泉驿微米黑等）。

### Q: AI 翻译很慢怎么办？
A: 
- 增加**并发线程数**（推荐 5~10）
- 增加**批量大小**（推荐 10~20）
- 选择响应速度更快的模型和供应商

---

## 技术原理

1. **GPAK 解析** — 游戏数据打包在 `resources.gpak` 二进制文件中，工具解析其索引结构，提取 `data/text/*.csv` 文件
2. **CSV 处理** — 游戏 CSV 使用标准逗号分隔格式，包含 `KEY, en, notes, sp, fr, de, it, pt-br, schinese` 等列。工具将中文翻译写入 `schinese` 列
3. **AI 翻译** — 将多条英文文本打包为 JSON 格式发给 LLM，要求返回 `{key: 中文翻译}` 的 JSON，实现批量翻译
4. **字体转换** — 读取 TTF/OTF 字体的 TrueType glyf 表，转换为 SWF DefineFont3 格式，替换游戏中的 `unicodefont.swf`
5. **GPAK 重打包** — 将修改后的 CSV（和字体 SWF）替换进 GPAK 文件，保持其他文件不变

---

## 许可证

本项目仅用于学习和个人使用。游戏 Mewgenics 的所有权归 Edmund McMillen 和 Tyler Glaiel 所有。

---

## 致谢

- **Edmund McMillen & Tyler Glaiel** — Mewgenics 游戏开发
- **OpenAI / DeepSeek / 智谱AI / 阿里云** — AI 翻译能力支持
- 所有参与测试和反馈的玩家
