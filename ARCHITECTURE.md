# Language Coach Architecture

## Schema 22 lexical comparison editorial boundary

- `backend/lexical_compare*.py` owns the versioned reviewed foundation and the discoverable candidate registry.
- `backend/lexical_compare_data_ielts_charts.py` owns the reviewed IELTS chart-language batch; future editorial batches remain separate modules with their own structural and factual tests.
- `backend/lexical_compare_data_ielts_argument.py` owns reviewed IELTS argument links and stance vocabulary, including grammar and logic-specific regression checks.
- `backend/comparison_review.py` owns mutable local workflow state and applies fail-closed evidence and publication gates.
- Schema 22 keeps editorial workflow metadata separate from open/private dictionary indexes and learner review data.
- Dictionary examples and corpus observations are evidence sources; they do not automatically become editorial conclusions.
- Registry synchronization is idempotent and preserves local priorities, notes, decisions and completed reviews.
- `backend/comparison_training.py` derives versioned tasks from reviewed comparison content, while schema 23 stores attempts and links only wrong boundaries to ordinary review cards; FSRS remains owned by `review_scheduler.py`.
- `backend/comparison_training_audit.py` is the versioned correction-task decision ledger. Runtime publication fails closed to explicitly approved corrections, and `scripts/audit_comparison_training.py` verifies that the approved and published sets are identical.

## schema 16 口语边界

- `backend/speaking_training.py` 负责口语任务、尝试、文本规则观察、自评与复习链接，不访问网络或音频设备。
- `backend/speech_transcription.py` 是可选外部转写适配器；服务端只在用户请求时读取本机音频并发送，返回文本和提供方溯源。
- 浏览器 `MediaRecorder` 负责采集，服务端只接受白名单 MIME、限制大小并使用随机文件名；SQLite 只保存元数据和相对文件名。
- 音频目录默认位于数据库旁的 `speaking/`，可用 `LANGUAGE_COACH_AUDIO_DIR` 隔离测试或部署目录。
- 当前 `backend/server.py` 仍承担 HTTP 编排和文件生命周期，进入 beta 前应把口语路由进一步拆成独立 handler，并让测试通过统一夹具恢复可变的全局数据库路径。

本文记录当前真实架构、依赖边界和渐进拆分顺序。它不是未来架构效果图；未完成的模块不会被写成已经存在。

## 当前运行形态

```text
浏览器前端（原生 HTML/CSS/JS）
        |
        | JSON HTTP API v1
        v
本地 Python ThreadingHTTPServer
        |
        +-- SQLite 主数据库
        +-- data/backups 本机备份
        +-- RSS / 翻译 / AI 反馈 / 开放数据外部适配

Chrome / Edge 扩展（WXT + TypeScript）
        |
        +-- 使用本机授权令牌调用同一 API
```

主产品仍是本地优先的单用户 Web 应用。Windows 登录任务负责启动本地服务和内容更新；它不等同于多人云服务。

## 已建立的工程边界

| 模块 | 职责 | 允许依赖 |
| --- | --- | --- |
| `backend/versioning.py` | 应用、API、数据库目标版本 | `VERSION` 文件 |
| `backend/review_scheduler.py` | 统一复习队列、评分状态、调度快照和撤销 | SQLite review tables |
| `backend/migrations.py` | 有序、幂等、可追踪的 SQLite 升级 | SQLite，不依赖 HTTP 或产品界面 |
| `backend/backups.py` | 限定目录内的备份、完整性检查和恢复 | SQLite、文件系统，不依赖业务服务 |
| `backend/practice_state.py` | 活动训练生命周期与可解释训练处方 | SQLite，不依赖 HTTP 或界面 |
| `backend/output_training.py` | 输出任务、作答、规则反馈、自评、AI 反馈记录与决定 | SQLite，不依赖 HTTP 或前端 |
| `backend/ai_feedback.py` | OpenAI-compatible 请求、五维 JSON 和证据引用校验 | 环境配置、外部 HTTPS，不访问 SQLite |
| `backend/usage_contrasts.py` | 人工审核的近义词边界内容 | 静态可版本化数据，不访问用户数据库 |
| `backend/server.py` | 当前组合根、HTTP 路由和尚未抽离的业务 | 可依赖上述基础模块 |
| `frontend/app.js` | 当前页面状态、渲染和 API 调用 | API v1；后续按服务和视图拆分 |
| `browser-extension/` | 网页授权采集入口 | 公共本机 API，不直接访问 SQLite |

依赖方向必须保持为“路由/界面依赖领域和基础模块”，迁移、备份等底层模块不得反向导入 `server.py`。

## 版本兼容

- `VERSION` 是应用版本唯一来源。
- `API_VERSION` 表示前后端契约版本；破坏性接口变化必须提升该版本。
- `SCHEMA_VERSION` 与 `schema_migrations` 表共同描述数据库目标版本和实际版本。
- `/api/version` 与 `/api/health` 同时报告应用、API、目标数据库和实际数据库版本。
- 前端发现版本不一致时显示重启提示，不再静默运行旧后端。

## 数据保护

- 用户可在用户中心创建 SQLite 一致性备份。
- 每份备份创建后执行 `PRAGMA integrity_check`。
- 恢复前自动创建当前数据库的安全备份。
- 恢复接口只接受系统生成的文件名，不能读取备份目录之外的路径。
- 当前没有云同步、账号隔离或加密备份；这些能力不能由本机备份替代。
- AI 密钥只从本机环境读取；原文和答案只有在用户主动请求时才发送给所配置服务。
- AI 反馈与原答案分表保存，模型建议不能覆盖原作答；提供方、模型和提示版本必须可追溯。

## 渐进拆分顺序

不进行一次性重写。每次只抽一个稳定边界，并要求行为测试先通过：

1. `content`：来源注册、RSS、订阅和每日内容。
2. `practice`：考试题型、题目校验、作答和错题。
3. `lexicon`：开放词典、语境、词卡和翻译编排。
4. `profile`：用户设置、能力证据、校准和计划。
5. 前端 `api/state/views`：先抽 API 客户端，再按页面迁移渲染。

`server.py` 最终只保留配置加载、路由注册、依赖组装和进程生命周期。拆分期间旧公开函数可保留薄代理，避免一次破坏测试和导入脚本。

## 每版质量门槛

- 所有数据库变化必须进入迁移注册表，不新增散落的 `ALTER TABLE` 判断。
- 新接口必须包含成功、输入错误和权限/路径边界测试。
- 固定左侧栏及列表/详情左右布局属于不可回退的界面契约。
- 完整单元与集成测试、Python/JavaScript 语法检查和 `git diff --check` 必须通过。
- 核心浏览器 E2E、无障碍、视觉基线和性能预算仍是后续工程任务，不能用 DOM 字符串测试冒充。
