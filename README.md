# Language Coach

一个本地优先、面向语境学习与考试训练的语言学习工作台。

Language Coach 将文章阅读、词典查询、生词积累、一文多练、错题讲解和网页划词收集放在同一套学习流程中。当前版本优先强化英语，支持 IELTS、TOEFL、四级、六级、考研英语、专四、专八、GRE、GMAT 等训练风格；法语和西班牙语内容仍在后续规划中。

> 当前版本：`0.8.0-alpha.3`。项目仍处于 Alpha 阶段，数据结构和交互可能继续调整。

## 核心功能

### 两种学习模式

- 顶部可随时切换兴趣模式与备考模式，选择保存在本机。
- 兴趣模式优先订阅、新闻、文化和较短内容；备考模式优先当前考试匹配与深度训练价值。
- 当前模式已影响“今日内容”，但尚未接入完整动态画像或能力预测。

### 文章与阅读

- 文章池采用左侧标题列表、右侧内容详情的工作台布局。
- 按来源、主题、难度和考试适配度筛选文章，并生成每日推荐。
- 支持国际时政、公共政策、商业、科学和公共机构来源，并区分新闻报道、观点评论、学术解释、研究摘要、机构公告和文化内容。
- 来源注册表区分 RSS 自动更新、摘要跳转、浏览器授权摘录、本地字幕和公共领域全文；支持来源订阅和 5/15/30 分钟今日内容。
- 区分 RSS 摘要与完整正文，避免把摘要误当作原文。
- 原文始终保留；中文译文可按需显示、编辑和保存。
- 支持文章一键翻译、分段缓存和逐段原文/译文对照；未配置翻译服务时可手动按段添加。
- WordNet 英文释义和例句可按需批量翻译，中文逐条显示在对应英文下方并缓存；应用会区分 DeepL 已配置、已验证和验证失败。
- 查词会在已验证翻译服务可用时自动补充中文，不需要再手动点击“翻译中文义项”。
- WordNet 词条会显示单词直译、逐义项释义、近义词、反义词、语义关系和来自个人文章的可追溯搭配；没有数据时会明确标记来源缺失。
- 页面导航会同步浏览器历史，支持返回上一页；练习中心会自动载入或生成当前文章题目。
- 练习中心区分专项练习、单篇组合和整套模拟；反馈方式可独立选择训练模式或模考模式。
- 考试题型研究、版权边界、公开样题来源和模型路线记录在 `EXAM_QUESTION_RESEARCH.md`。
- IELTS 阅读已具备判断题、段落标题匹配、段落信息匹配和摘要填空四类独立模板；新题入库前校验证据、答案、选项和题型规则。
- 作答会记录题型、能力与结构化错因，练习中心只加载当前考试和专项的新题，避免历史通用题混入。
- 自动整理段落、移除重复标题，并识别环境、健康、科技、历史等主题。
- 阅读时可点词查询，并将单词连同原句保存到生词本。

### 词汇中心

- 支持英文、中文、词形、词根、词缀和拉丁词源混合查询。
- 展示英美音标与发音、构词拆解、词源、词族和派生关系。
- 展示双语搭配、近义词组、反义词组与真实语境例句。
- 自动高亮查询词、词形变化和可识别的派生词。
- 生词保存语境，而不只保存孤立释义。
- 生词本区分单词与短语；文章分析按当前临时等级、词典等级和生词记录推荐可能不认识的表达。
- 任意英文单词或最多六词短语即使未被本地词典收录，也能继续翻译、保存、查看个人文章语境或跳转欧路。
- 生词卡可重新进入查询并返回来源文章；重复保存会更新原卡片而不是创建副本。
- 已导入 Open English WordNet 2025：提供英文义项、音标、例句、同义词和上下位语义关系，并显示 CC BY 4.0 来源。

### 练习与复盘

- 同一篇文章可按考试专项生成判断、匹配、摘要填空和通用选词练习；首字母填空已移除。
- 支持 IELTS、TOEFL、四级、六级、考研英语、专四、专八、GRE、GMAT 和通用出题风格。
- IELTS 整套模拟按三篇文章和 40 题组织，当前采用 13 / 13 / 14 的规则分配，需要三篇本地完整文章。
- 做题时保留左侧原文，支持题号导航、标记、计时以及逐题/全部显示。
- 训练模式答题后立即展示答案、证据和考点讲解；模考模式统一交卷后再揭晓。
- 交卷结果展示正确率、完成度、用时、能力项和错因分布，未作答题不会从统计中消失。
- 题库区分官方公开链接、用户自有材料和系统模拟题，不把未授权网络真题复制进项目。
- 可针对同一考点生成巩固题，并将错题收入复盘列表。
- 使用 XP、等级和连续学习天数记录学习进度。

### 浏览器扩展

- 在网页中划词查询和保存生词。
- 选中段落后请求翻译，并保存原文、译文、上下文、标题和 URL。
- 从网页右键菜单提取主要正文，导入 Language Coach 文章池。
- 本地连接使用随机令牌保护；翻译密钥只保存在后端进程环境中。

## 技术架构

```text
language-coach/
├── backend/             Python HTTP API、业务逻辑与 SQLite 持久化
├── frontend/            原生 HTML、CSS 和 JavaScript 前端
├── browser-extension/   WXT + TypeScript 浏览器扩展
├── tests/               Python 集成测试
├── data/                本地运行数据（数据库不进入 Git）
├── run.ps1              PowerShell 启动脚本
└── start-language-coach.bat
```

应用后端仅使用 Python 标准库，核心数据保存在本地 SQLite 中。浏览器扩展使用 WXT、TypeScript 和 Defuddle。

## 快速启动

### 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- 构建扩展时需要 Node.js 20+ 与 pnpm

### 启动应用

克隆仓库后，在项目目录运行：

```powershell
.\run.ps1
```

也可以双击 `start-language-coach.bat`。默认访问地址：

```text
http://127.0.0.1:8765/
```

若要使用其他端口：

```powershell
python .\backend\server.py 8766
```

首次运行会自动创建 `data/language_coach.sqlite`。该数据库已被 `.gitignore` 排除。

## 构建浏览器扩展

```powershell
cd browser-extension
pnpm install
pnpm build:edge
```

构建产物位于 `browser-extension/.output/edge-mv3`。

在 Edge 的 `edge://extensions` 或 Chrome 的 `chrome://extensions` 中开启开发者模式，选择“加载解压缩的扩展”，然后指向上述目录。回到 Language Coach 的生词本页面复制本地连接令牌，并在扩展设置中保存和测试连接。

扩展也可以在开发模式下运行：

```powershell
pnpm dev
```

## 翻译配置

查词、网页正文提取和保存不需要第三方密钥。复制 `.env.example` 为不会提交到 Git 的 `.env.local`。DeepL API Free 配置示例：

```dotenv
TRANSLATION_PROVIDER=deepl
DEEPL_API_KEY=your-deepl-api-key
```

免费自托管方案可使用 LibreTranslate：

```dotenv
TRANSLATION_PROVIDER=libretranslate
LIBRETRANSLATE_URL=http://127.0.0.1:5000
```

修改后重启服务。翻译结果按文本、语言和服务商缓存在本地 SQLite 中。API Key 不会写入浏览器扩展、数据库或 Git 仓库；没有可用提供商时仍可手动逐段添加译文。

## 测试

运行后端与学习流程测试：

```powershell
python -m unittest discover -s tests -v
```

本地服务启动后，可使用捆绑或已安装的 Playwright 运行练习中心浏览器冒烟测试：

```powershell
node .\scripts\verify_practice_ui.cjs http://127.0.0.1:8765/
```

检查扩展类型并构建 Edge 版本：

```powershell
cd browser-extension
pnpm typecheck
pnpm build:edge
```

## 词典与内容来源

### 导入 Open English WordNet

项目提供可重复运行的导入器。先准备官方 2025 JSON ZIP，再运行：

```powershell
python .\scripts\import_wordnet.py --zip .\artifacts\english-wordnet-2025-json.zip
```

也可以让导入器下载官方版本：

```powershell
python .\scripts\import_wordnet.py --download
```

导入结果写入本地 SQLite，不会把词典压缩包或生成的数据库提交到 Git。查询页会显示 Open English WordNet 的英文义项、例句、语义关系、版本和 `CC BY 4.0` 来源信息；中文释义仍通过 DeepL 或手动译文补充。

当前仓库内置的是用于验证学习闭环的结构化示例词条，不是对 Oxford、Cambridge 或 Collins 等商业词典的复制。后续词典扩充优先采用许可清晰的 Wiktionary/Kaikki、WordNet、Tatoeba 等开放数据；商业词典仅通过授权 API 或外部链接接入。

文章来源会记录标题、来源、原始地址和内容完整性状态。RSS 只提供摘要时，界面会明确标记并引导打开原始来源，不会伪装成完整文章。

## 第三方项目边界

浏览器扩展采用以下开源基础：

- [WXT](https://github.com/wxt-dev/wxt)：MIT License
- [Defuddle](https://github.com/kepano/defuddle)：MIT License

[Read Frog（陪读蛙）](https://github.com/mengxi-ream/read-frog)用于产品与扩展架构评估。Language Coach 没有复制其 GPL-3.0 业务代码。完整说明见 [`browser-extension/THIRD_PARTY_NOTICES.md`](browser-extension/THIRD_PARTY_NOTICES.md)。

## 版本管理

项目使用 Semantic Versioning，并通过 Git 标签保留发布节点：

- 稳定版本：`vMAJOR.MINOR.PATCH`
- 预发布版本：`vMAJOR.MINOR.PATCH-alpha.N`
- 提交信息：遵循 Conventional Commits，例如 `feat:`、`fix:`、`docs:`、`test:`、`chore:`

版本历史见 [`CHANGELOG.md`](CHANGELOG.md)，当前版本见 [`VERSION`](VERSION)。产品定位、路线图、真实完成状态、关键决定和相关项目调研分别见 [`PRODUCT.md`](PRODUCT.md)、[`ROADMAP.md`](ROADMAP.md)、[`STATUS.md`](STATUS.md)、[`DECISIONS.md`](DECISIONS.md) 和 [`RESEARCH.md`](RESEARCH.md)。

## 路线图

- 扩充许可清晰的开放词典数据，并标注每条释义来源。
- 增加 URL、PDF、字幕和批量文章导入。
- 建立考试套题、题型专题和难度校准体系。
- 增加听力逐词高亮、跟读和影视片段学习。
- 增加法语、西班牙语内容与相应分级体系。
- 提供 PWA 离线缓存和更完整的移动端体验。

## 数据与安全

- SQLite 数据库、扩展构建产物、依赖目录和本地密钥不会提交到 Git。
- 不要把 `DEEPL_API_KEY`、本地连接令牌或其他凭据写入源码。
- 当前仓库尚未声明项目整体开源许可证；第三方依赖继续遵循各自许可证。
