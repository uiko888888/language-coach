# Related Project Research

调研日期：2026-07-16。星标为调研时的近似值，后续会变化。调研用于提取产品机制，不代表复制实现。

学习模式的统一对比、证据等级和 Complete the Words 卡片回顾边界见 [`COMPETITIVE_MODE_MATRIX.md`](COMPETITIVE_MODE_MATRIX.md)。
2026-07-21 六轮机制调研与采用优先级见 [`RESEARCH_ROUNDS_2026-07-21.md`](RESEARCH_ROUNDS_2026-07-21.md)。

## 2026-07-17 - TOEFL 2026 Complete the Words 核验记录

- 已采用的信息：`Complete the Words` 作为 2026 TOEFL 阅读任务名称，训练目标涉及上下文词汇识别与完整拼写。
- 官方入口：https://www.ets.org/toefl/test-takers/ibt/about/content/reading.html
- 本次核验状态：开发环境无法连接 ETS 官网，不能确认最新页面中的多空数量、字母显示比例、计时和计分细则。
- 当前实现：一题一个目标词，显示规则前缀并隐藏后续字母，要求输入完整单词；生成来源为 `toefl-2026-sim-v1`，`official_equivalence=false`。
- 后续复核：以 ETS 官方公开说明或用户提供的官方公开样题为准，核验后再实现多空任务、精确界面和评分。不得使用培训机构转述替代官方规格。

## 值得借鉴的项目

### Read Frog

- 仓库：https://github.com/mengxi-ream/read-frog
- 约 8.5k stars，GPL-3.0
- 可借鉴：选词工具栏、上下文翻译、自定义 AI 动作、多模型适配、请求批处理与失败重试。
- 边界：只借鉴产品与架构思想，不复制 GPL-3.0 业务代码。

### LUTE

- 仓库：https://github.com/LuteOrg/lute-v3
- 约 1.5k stars，MIT
- 可借鉴：以文本为课程、词汇熟悉状态、已知词覆盖率与阅读材料难度联动。

### asbplayer

- 仓库：https://github.com/asbplayer/asbplayer
- 约 1.3k stars，MIT
- 可借鉴：字幕列表定位、自动暂停、跳过无字幕区间、播放速度控制、字幕偏移、句子采集、词汇状态高亮和理解率。
- 适用：Language Coach 的字幕导入、逐句听力和流媒体学习工作台。

### LinguaCafe

- 仓库：https://github.com/simjanos-dev/LinguaCafe
- 约 1.4k stars，GPL-3.0
- 可借鉴：阅读、即时查词、词汇状态和后续复习的连续流程。
- 边界：不复制 GPL-3.0 实现。

### FSRS

- 仓库：https://github.com/open-spaced-repetition/free-spaced-repetition-scheduler
- 约 690 stars，MIT
- 可借鉴：根据记忆难度、稳定性和可提取性调度词汇、词块、错题和听力句子复习。

### IELTS Atlas

- 仓库：https://github.com/sallowayma-git/IELTS-practice
- 约 500 stars，GPL-3.0
- 可借鉴：题库导入、单篇与套题、练习记录、错题雷达、本地备份和每日总览。
- 风险：项目明确提示题源、音频和 PDF 存在第三方版权风险。不得复用其题库或受保护素材。

## 有价值但不直接采用的模式

部分 AI 考试项目使用以下职责拆分：

```text
Planner -> Generator -> Validator -> Corrector -> Analytics
```

Language Coach 可采用相同的质量控制思想，但用自己的数据结构和实现：

```text
素材分析器
-> 练习规划器
-> 题目生成器
-> 答案与证据校验器
-> 错题讲解器
-> 画像更新器
-> 复习调度器
```

## 产品机会

现有工具通常只覆盖阅读、字幕、复习或题库中的一个环节。Language Coach 的差异化机会是：

- 兴趣模式和备考模式共享动态画像。
- 字幕、访谈、新闻、小说和博客进入同一素材图谱。
- 同一素材可以生成阅读、听力、词汇、复述和考试训练。
- 每一道模拟题保留来源、证据、能力标签和生成版本。
- 用户投入用 XP 表示，真实能力用独立指标表示。
- 推荐说明“为什么适合现在的你”，并允许用户纠正。

## 2026-07-18 - 双模式与画像校准机制综合

- LUTE 的核心启发是按文本和词汇熟悉度记录局部证据，不把“读过内容”直接等同于综合语言等级。
- FSRS 适合记忆项目的复习调度，但记忆稳定性不是 IELTS、TOEFL 或 CEFR 能力分；不能直接拿 FSRS 分数替代语言画像。
- EF SET 类低负担测试适合建立初始锚点，但持续画像仍需要用户后续真实训练证据。
- asbplayer 等字幕工具能提供重播、速度、字幕和句子采集事件；这些事件未来只应更新听力或词汇分项，观看时长本身不能提高综合等级。
- 成熟自适应系统通常区分题目难度、能力维度、样本量和置信区间。当前实现先采用可解释的有界规则，待数据量足够后再评估 IRT/BKT，不用不透明模型提前制造精确感。

本轮采用“七天周期 + 分项证据 + 综合覆盖门槛”。这是项目自己的产品规则，不声称复刻任何商业软件的专有算法。

## 采用原则

1. 优先采用许可证清晰的通用基础和算法。
2. GPL/AGPL 项目只做研究，除非整个衍生模块接受相同许可并经过明确决策。
3. 不导入来源不明的真题、音频、字幕、PDF 或商业词典数据。
4. 借鉴考试结构与教学机制，不复制具体题目表达。
5. 引入第三方依赖前记录许可证、维护状态、数据流和替换方案。

## 开放词汇与语境数据规划

词汇中心不使用单一来源冒充完整词典，而是让不同开放数据各自负责一个维度：

- [Open English WordNet](https://github.com/globalwordnet/english-wordnet)：核心义项、词性、同义词组和语义关系。导入时保留版本与许可证归属。
- [Wiktionary / Kaikki](https://kaikki.org/dictionary/)：音标、词形、词源、构词信息、短语和部分例句。其衍生数据需要保留署名及相同方式共享等许可要求，导入器必须逐条记录来源。
- [Tatoeba](https://tatoeba.org/)：带语言配对的真实例句候选。只导入许可和署名信息完整的句子，并做长度、自然度、敏感内容和翻译一致性筛选。
- 用户文章、字幕与浏览器摘录：提供真正属于用户学习历史的语境、重复查询次数和个人高频搭配，不公开再分发受版权保护的上下文。
- YouGlish、商业语料库和商业词典：只提供外部检索入口或使用正式授权 API，不抓取或复制其内容库。

“日常最常用词义”不能只靠词典排列顺序判断。计划中的排序信号为：开放语料频率、当前内容池出现频率、用户查询/保存次数、语域（日常/正式/学术）、搭配覆盖和当前语境匹配。页面按以下层级展示：

```text
当前语境中的意思
-> 日常最常用义
-> 常见搭配和词块
-> 近义表达的使用差别
-> 反义与易混表达
-> 词源、词根和词族
-> 来自用户素材的真实例句
```

目标不是增加释义数量，而是让用户先理解英语中的概念、搭配和使用条件，再按需查看中文确认。

## 2026-07-17 - 可内置英语词典数据审计

本次优先查英语，结论按“能否随 Language Coach 一起分发”而不是“网页能否免费打开”判断。

### 第一批可以落地

| 数据 | 适合承担的维度 | 许可证/分发判断 | 结论 |
| --- | --- | --- | --- |
| [Open English WordNet](https://github.com/globalwordnet/english-wordnet) | 词性、同义词集、反义关系、上下位关系、词族网络 | 2025 版 README 标明 CC BY 4.0，并提供 JSON、LMF、RDF、WNDB 下载 | 首批导入；作为语义关系底座 |
| [Kaikki / Wiktionary machine-readable data](https://kaikki.org/dictionary/English/index.html) | 音标、词形、词源、词根词缀、短语、多义项和部分例句 | 数据来自 Wiktionary；需按 CC BY-SA/GFDL 之一完成署名、许可证和衍生数据义务。英语站点当前页面列出约 138 万词形，整套旧 JSONL 约 3GB | 过滤导入；不把整套 3GB 放进 MVP 仓库 |
| [Tatoeba](https://tatoeba.org/en/terms_of_use) | 英语与中文/其他语言的真实例句配对 | 文本句子默认 CC BY 2.0 FR，必须保留作者署名；音频可能有不同许可证，不能一概导入 | 先导入文本例句；每条保留作者和许可证 |
| [FreeDict](https://freedict.org/) | 双语词典、基础释义、部分短语；TEI XML 便于转换 | 项目提供 140+ 本、约 45 种语言的自由词典，但具体词典和来源必须逐本核对 | 作为法语/西语和少量英语双语补充，不假设存在高质量英汉库 |
| [Moby Thesaurus](https://www.gutenberg.org/ebooks/3202) | 同义词、相关词和写作联想 | Project Gutenberg 页面标为美国公版；其他国家/地区仍需确认，且内容较旧 | 可选导入同义关系，必须标注“美国公版来源” |

### 可以使用，但不能当词典

- [wordfreq](https://github.com/rspeer/wordfreq)：适合给义项和词组排序。代码使用 Apache 许可证，数据包含 CC BY-SA 4.0 和 Google Books N-gram 等来源，必须保留 NOTICE 和来源说明。它只能说明“常见程度”，不能提供可靠释义。
- 用户自己的文章、字幕和浏览器摘录：最适合计算个人高频词、重复查询和真实搭配，但受版权保护的正文只保存在用户本地，不进入公共数据包。

### 暂不作为第一批内置

- Princeton WordNet：可免费使用但有专门许可和署名条款；Open English WordNet 已提供 CC BY 4.0 的现代替代，优先采用后者。
- GCIDE：历史性和公版内容混杂，工程上需要拆分数据来源及 GPL/GFDL 义务，先不放入基础包。
- OpenSubtitles、COCA、商业语料和影视字幕：来源和再分发边界复杂，不能因为网上能下载就直接打包。
- Oxford、Cambridge、Collins、Longman、欧路：商业词典内容不能抓取后内置；可以通过授权 API、外部链接或用户自己的合法查询使用。

### 推荐导入顺序

```text
alpha.12 Open English WordNet 语义关系（本轮完成）
alpha.13 文章导入与合辑
alpha.14 Kaikki/Wiktionary 精选词条：B1-C1、常用词、短语、音标、词源
alpha.15 Tatoeba 英汉例句与许可证记录
alpha.16 wordfreq 频率排序和个人语境排序
```

### 内置数据必须保留的元数据

每个词条、义项、例句和关系都要保存：`source_name`、`source_version`、`license`、`attribution`、`source_url`、`checksum`。这样查询页面可以告诉用户某个释义来自哪里，也能在以后替换数据而不污染用户自己的学习记录。
