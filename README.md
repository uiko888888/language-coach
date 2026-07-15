# Language Coach v2

本版本是正式版骨架：本地 Web 应用 + Python API + SQLite 数据库。

## 运行

Windows 可以直接双击 `start-language-coach.bat`，并保持服务器窗口打开。

也可以使用 PowerShell：

```powershell
cd C:\Users\hususu\Documents\Codex\2026-07-15\new-chat\outputs\language-coach-v2
.\run.ps1
```

打开：

```text
http://127.0.0.1:8765
```

## 已有模块

- 文章池：考试型 RSS 来源、匹配度排序、搜索和个人导入。
- 文章发现：按来源主题筛选，并从现有文章池选出每日三篇推荐，展示推荐理由与分数。
- 文章主题与格式：根据正文识别环境保护、健康医学、太空探索等内容主题；正文去除重复标题、自动分段并首行缩进。
- 内容完整性：明确区分 RSS 摘要和完整正文；摘要可打开原始来源或补充正文，RSS 提供完整内容时自动升级。
- 阅读台：文章分级、重点词、重点句、点词加入生词本。
- 一文多用：阅读题、选词填空、首字母填空、综合拆解。
- 出题风格：IELTS、TOEFL、专四、专八、GRE、GMAT、通用。
- 生词本：词和语境入库。
- 错题本：答错后实时讲解，记录答案和证据，并生成同考点巩固题。
- 左右工作台：文章/错题标题在左侧列表，选中内容在右侧显示。
- 顶部查词：在任意页面搜索英文、中文、词形、词根或拉丁词源。
- 词汇中心：左右词典工作台，包含英美音标与发音、构词拆解、词源、词族、双语搭配、近反义词组和双语例句。
- 语境高亮：例句自动标粗当前查询词、词形变化和已收录的派生词。
- 文章联动：文章内点词使用同一词典，并可连同原句加入生词本。
- 双语阅读器：原文始终保留，译文按需显示并可编辑保存；没有可靠译文时不会生成伪翻译。
- 考试题型：IELTS、TOEFL、专四、专八、GRE、GMAT 各自显示对应题型，做题时左侧固定保留原文。
- 学习进度：首次答题和首次完成错题复盘获得 XP，并记录等级与连续学习天数。
- 全文查词：阅读文本可直接点词，其他英文内容可双击单词或选中短语进入全局查询。
- 浏览器插件：网页划词查词、选段翻译，并将原文、译文、上下文、标题和地址保存到本地生词本。

## 浏览器插件

插件源码位于：

```text
browser-extension
```

构建并加载插件：

```powershell
cd browser-extension
pnpm install
pnpm build:edge
```

在 Edge 的 `edge://extensions` 或 Chrome 的 `chrome://extensions` 中开启开发人员模式，选择“加载解压缩的扩展”，指向 `browser-extension/.output/edge-mv3`。然后进入 Language Coach 的“生词本”，复制本地连接令牌，并在扩展设置中保存和测试连接。

插件使用 WXT + TypeScript，并使用 Defuddle 提取网页主要正文。两者均采用 MIT License。陪读蛙（Read Frog）仅用于架构评估，没有复制其 GPL-3.0 业务源码，具体边界见 `browser-extension/THIRD_PARTY_NOTICES.md`。

查词与保存不需要第三方密钥。启用选段翻译时，在启动服务前配置 DeepL：

```powershell
$env:DEEPL_API_KEY="your-deepl-api-key"
python .\backend\server.py 8766
```

翻译结果按文本、语言和服务商缓存在本地 SQLite 中。API Key 只存在于后端进程环境，不会写入扩展或 Git。

## 词典数据

`v0.5.0` 首批词条是项目内维护的结构化示例数据，用于验证完整学习闭环，尚不是大规模商业词典。
后续扩充优先采用 Wiktionary/Kaikki、WordNet、Tatoeba 等许可清晰的数据源；Oxford、Cambridge、Collins 等内容只通过授权 API 或外部链接接入，不直接抓取网页释义。

可直接打开词汇查询：

```text
http://127.0.0.1:8765/?view=lexicon&q=spect
```

## 数据位置

```text
data/language_coach.sqlite
```

## 后续扩展

- 批量导入开放词典数据并增加词义来源标注。
- 加 PDF、网页、字幕导入。
- 加 AI 解析、AI 出题和题目难度校准。
- 做 PWA 离线缓存和手机访问。
- 后续可迁移到 React/Vite，后端和数据库结构可以继续沿用。
