# Language Coach v2

本版本是正式版骨架：本地 Web 应用 + Python API + SQLite 数据库。

## 运行

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

## 数据位置

```text
data/language_coach.sqlite
```

## 后续扩展

- 接入更强的词典解释、词根、搭配、近义词 API。
- 加 PDF、网页、字幕导入。
- 加 AI 解析、AI 出题和题目难度校准。
- 做 PWA 离线缓存和手机访问。
- 后续可迁移到 React/Vite，后端和数据库结构可以继续沿用。
