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
- 阅读台：文章分级、重点词、重点句、点词加入生词本。
- 一文多用：阅读题、选词填空、首字母填空、综合拆解。
- 出题风格：IELTS、TOEFL、专四、专八、GRE、GMAT、通用。
- 生词本：词和语境入库。
- 错题本：答错后实时讲解，记录答案和证据，并生成同考点巩固题。
- 左右工作台：文章/错题标题在左侧列表，选中内容在右侧显示。
- 顶部查词：在任意页面搜索英文、中文、词形、词根或拉丁词源。
- 词汇中心：左右词典工作台，包含英美音标与发音、构词拆解、词源、词族、搭配、近反义词和例句。
- 文章联动：文章内点词使用同一词典，并可连同原句加入生词本。

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
