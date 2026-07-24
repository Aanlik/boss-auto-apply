# BOSS 直聘自动求职工作台设计

## 背景
当前项目已经验证了“能跑起来”的基础，但信息架构和界面组织仍然失控：页面像功能集合，而不是一个可操作的求职工作台。用户真正需要的是一条清晰主线，而不是一堆互相脱节的面板。

这个产品的定位仍然保持不变：

- 面向求职者，不是招聘方
- AI 负责解析、排序、生成建议
- 人工负责最终确认、编辑和发送
- 简历和岗位必须通过同一条数据链路关联

参考项目的作用也重新明确：

- `jlifeng/JobPilot`：参考本地优先工作台、AI 工具调用、逐条应用修改、可编辑的岗位匹配流程
- `Kiranism/next-resume-ai`：参考简历导入、ATS 风格、岗位定制与 PDF 导出
- `olyaiy/resume-lm`：参考简历管理、评分、话术和版本化思路
- `sdn9300/Align-Resume`：参考匹配评分、真实改写、缺口分析和 guardrail
- `MadsLorentzen/ai-job-search`：参考求职者端的岗位评估、简历定制、求职工作流组织
- `santifer/career-ops`：参考求职者端的岗位扫描、打分、简历定制、申请跟踪
- `feder-cr/Jobs_Applier_AI_Agent_AIHawk`：参考求职者端的自动化申请框架、批量岗位处理和定制化投递思路

其中岗位能力要拆成两层：

- **岗位抓取**：从 Boss 页面或接口把岗位列表、详情、JD、公司信息抓出来
- **岗位识别**：把原始抓取结果标准化成可用的岗位记录，并提取关键词、城市、薪资、JD 结构

岗位来源入口不只一个：

- 手动录入：用于冷启动、补录和校正抓取结果
- 抓取导入：用于从 Boss 页面批量导入岗位
- 外部导入：用于未来接入其他岗位源

识别层只做一件事：把这些来源统一成同一种岗位结构，再交给后续模块。

这些项目都站在求职者端，适合拿来参考“怎么筛岗位、怎么评估岗位、怎么把简历和 JD 连起来”。`JobPilot` 仍然是我们最重要的 JD 分析和匹配参考。

## 目标

1. 先重构工作台 UI，而不是继续堆功能按钮。
2. 建立一条明确的主链路：岗位抓取 -> 岗位识别/标准化 -> 选择目标岗位 -> 读取 JD -> 简历解析 -> 简历优化 -> 尽调 -> 评分 -> 话术 -> 人工确认发送。
3. 所有模块共用同一份岗位和简历数据，避免多份状态互相打架。
4. AI 只做建议和排序，不自动发送。
5. 每个模块都必须有空状态、加载状态、错误状态和人工确认入口。

## 非目标

- 不做无确认的自动发送。
- 不做以营销展示为主的首页。
- 不把页面做成卡片堆叠的仪表盘。
- 不在第一阶段加入多账号、团队协作、复杂 CRM。
- 不把平台反检测、风控绕过作为产品卖点。

## 设计原则

1. 工作台优先，不做 landing page。
2. 只保留一个“当前目标岗位”。
3. 简历优化必须从岗位 JD 读取信息，不允许再靠手填标题代替。
4. 所有 AI 输出都要能被人工查看和修正。
5. UI 以扫描效率为主：信息密度高、层级清晰、状态明确。
6. 同一类数据只出现一个主入口，避免多个页面重复修改同一实体。

## 核心实体

### 简历

- 基础信息
- 技能
- 工作经历
- 项目经历
- 教育经历
- 简历优化建议

### 岗位

- id
- 原始抓取来源
- 标题
- 公司
- 城市
- 薪资
- 完整 JD
- 关键词
- 结构化摘要
- 状态：未选中 / 已选中 / 已进入待发送

### 岗位来源记录

- source_type：手动录入 / 抓取导入 / 外部导入
- source_id：来源内唯一标识
- raw_payload：原始数据
- fetched_at：抓取或导入时间
- normalized_job_id：归一化后岗位 id
- dedupe_key：去重键

### 公司资料

- company_name
- source_context
- website / 招聘页 / 备注
- user_notes
- fetched_at
- ai_search_queries
- ai_search_sources
- ai_search_summary
- research_priority
- research_status
- canonical_source

### 公司尽调

- 风险等级
- 行业前景
- 证据列表
- 一句话结论

公司尽调的入口和输入：

- 入口一：岗位卡片里的“尽调”按钮
- 入口二：岗位详情页里的右侧信息栏
- 入口三：排序页里对未尽调岗位的补全入口
- 输入：公司名、JD、岗位标题、城市、岗位来源记录、用户补充备注、AI 搜索到的互联网资料
- 输出：风险等级、行业前景、证据列表、一句话结论、可解释备注

尽调的实现方式不是纯聊天输出，而是“AI 搜索互联网 + 结构化信号 + AI 归纳”：

- 先用 AI 搜索互联网，收集公司基本信息、舆情、产品、融资、技术栈和招聘上下文
- 再把搜索结果加工成可读证据和结构化信号
- 最后让 AI 把信息归纳成风险、前景和结论，并允许人工补充证据和纠正结论

### 排名结果

- 岗位匹配分
- 公司分
- 行业分
- 综合分
- 排序位置

### 话术与发送

- 打招呼语草稿
- 人工编辑稿
- 确认发送状态
- 发送回执

## 字段总表

### Job

| 字段 | 说明 |
|---|---|
| `job_id` | 统一岗位 id |
| `source_id` | 原始来源记录 id |
| `title` | 岗位标题 |
| `company` | 公司名 |
| `city` | 城市 |
| `salary` | 薪资 |
| `jd_text` | 完整 JD |
| `keywords` | JD 关键词 |
| `summary` | 结构化摘要 |
| `status` | 岗位状态 |

### Resume

| 字段 | 说明 |
|---|---|
| `profile_id` | 简历画像 id |
| `name` | 姓名 |
| `title` | 当前标题 |
| `skills` | 技能列表 |
| `experience_blocks` | 工作经历块 |
| `project_blocks` | 项目经历块 |
| `education_blocks` | 教育经历块 |
| `raw_text` | 原始文本 |
| `parse_status` | 解析状态 |

### Research

| 字段 | 说明 |
|---|---|
| `research_id` | 调研记录 id |
| `company_name` | 公司名 |
| `queries` | 搜索词 |
| `sources` | 资源列表 |
| `source_snippets` | 来源摘要 |
| `evidence_items` | 证据条目 |
| `summary` | 调研摘要 |
| `status` | 调研状态 |

### Diligence

| 字段 | 说明 |
|---|---|
| `company_name` | 公司名 |
| `research_queries` | 调研词 |
| `research_sources` | 调研来源 |
| `evidence_items` | 证据 |
| `risk_level` | 风险等级 |
| `industry_outlook` | 行业前景 |
| `conclusion` | 结论 |
| `editable_note` | 人工修正备注 |

### Score

| 字段 | 说明 |
|---|---|
| `job_id` | 岗位 id |
| `match_score` | 匹配分 |
| `company_score` | 公司分 |
| `industry_score` | 行业分 |
| `total_score` | 综合分 |
| `rank_index` | 排序位置 |
| `score_reason` | 解释 |

### Message / Send

| 字段 | 说明 |
|---|---|
| `job_id` | 岗位 id |
| `draft_text` | 草稿 |
| `edited_text` | 编辑稿 |
| `confirm_status` | 确认状态 |
| `send_status` | 发送状态 |
| `receipt_id` | 回执 id |

## 后端模型映射

| 领域 | 建议模型名 | 说明 |
|---|---|---|
| 岗位 | `JobRecord` | 归一化后的岗位实体 |
| 岗位来源 | `JobSourceRecord` | 原始来源与抓取记录 |
| 简历 | `ResumeProfile` | 解析后的简历画像 |
| 调研 | `InternetResearchRecord` | 互联网调研结果 |
| 尽调 | `CompanyDiligenceRecord` | 尽调加工后的结构化结论 |
| 评分 | `ScoreRecord` | 综合评分结果 |
| 话术 | `MessageDraft` | 招呼语和编辑稿 |
| 发送 | `SendRecord` | 确认发送回执与状态 |

## API 草案

### `POST /api/jobs/capture`

- 请求：`source_type`、`page_cursor`、`search_keyword`、`filters`
- 响应：`capture_id`、`raw_items`、`next_cursor`、`status`、`errors`

字段校验：

- `source_type` 必填，取值必须在支持来源内
- `page_cursor` 可空，空时从第一页开始
- `search_keyword` 可空，但 `filters` 不能为空时仍允许抓取
- `filters` 必须为对象

```json
{
  "source_type": "boss",
  "page_cursor": "2",
  "search_keyword": "Python"
}
```

```json
{
  "status": "ok",
  "capture_id": "cap_001",
  "next_cursor": "3",
  "raw_items": []
}
```

### `POST /api/jobs/normalize`

- 请求：`raw_items`、`source_type`
- 响应：`jobs`、`deduped_count`、`status`、`errors`

字段校验：

- `raw_items` 必填，且不能为空数组
- `source_type` 必填
- 每条 `raw_item` 必须包含最少的标题、公司或 JD 之一

### `POST /api/resumes/parse`

- 请求：文件或文本
- 响应：`profile`、`parse_status`、`errors`

字段校验：

- 文件与文本二选一，至少提供一个
- 文件大小应有限制，超限直接返回 `INVALID_INPUT`

### `POST /api/resumes/optimize`

- 请求：`profile_id`、`target_job_id`
- 响应：`summary`、`bullets`、`matched_keywords`、`missing_keywords`、`status`、`errors`

字段校验：

- `profile_id` 必填
- `target_job_id` 必填
- 两者都必须对应已存在记录

### `POST /api/research/run`

- 请求：`company_name`、`job_id`、`jd_text`、`search_scope`
- 响应：`research_id`、`queries`、`evidence_items`、`status`、`missing_coverage`、`errors`

字段校验：

- `company_name` 必填
- `job_id` 必填
- `jd_text` 必填
- `search_scope` 可空，默认 `default`

```json
{
  "company_name": "示例科技",
  "job_id": "job_001",
  "jd_text": "负责 Python 后端开发",
  "search_scope": "default"
}
```

```json
{
  "status": "partial",
  "research_id": "res_001",
  "queries": ["示例科技 官网", "示例科技 融资"],
  "missing_coverage": ["招聘页"],
  "evidence_items": []
}
```

### `POST /api/diligence/evaluate`

- 请求：`research_id`、`job_id`、`company_notes`
- 响应：`risk_level`、`industry_outlook`、`evidence_items`、`conclusion`、`editable_note`、`status`、`errors`

字段校验：

- `research_id` 必填
- `job_id` 必填
- `company_notes` 可空

### `POST /api/scoring/rank`

- 请求：`resume_id`、`jobs`、`diligences`
- 响应：`ranked_jobs`、`sort_rules`、`status`、`errors`

字段校验：

- `resume_id` 必填
- `jobs` 必填且不能为空数组
- `diligences` 可空，但若为空时必须返回 `partial`

### `POST /api/messages/draft`

- 请求：`job_id`、`resume_id`、`diligence_id`
- 响应：`draft_text`、`edited_text`、`status`、`errors`

字段校验：

- `job_id` 必填
- `resume_id` 必填
- `diligence_id` 必填

### `POST /api/send-inbox/confirm`

- 请求：`job_id`、`draft_id`、`confirm_token`
- 响应：`send_status`、`receipt_id`、`status`、`errors`

字段校验：

- `job_id` 必填
- `draft_id` 必填
- `confirm_token` 必填

```json
{
  "job_id": "job_001",
  "draft_id": "draft_001",
  "confirm_token": "token_abc"
}
```

```json
{
  "status": "ok",
  "send_status": "sent",
  "receipt_id": "rcp_001"
}
```

### API 状态与错误码

统一响应建议包含：

- `status`：`ok` / `partial` / `failed`
- `errors[]`：结构化错误列表
- `warnings[]`：可继续但需要注意的提醒

统一错误码建议：

- `INVALID_INPUT`：请求字段不合法
- `NOT_FOUND`：目标记录不存在
- `UNAUTHORIZED`：未授权或登录失效
- `EMPTY_RESULT`：没有搜索结果或筛选结果
- `PARTIAL_RESULT`：只有部分结果可用
- `SEARCH_TIMEOUT`：研究或抓取超时
- `DUPLICATE_RECORD`：重复导入或重复提交
- `STATE_BLOCKED`：状态不允许继续
- `SEND_FAILED`：发送失败
- `INTERNAL_ERROR`：未知内部错误

状态约定：

- `ok`：正常完成
- `partial`：有可用结果但不完整
- `failed`：本次步骤失败，需要重试或修正

统一返回包：

```json
{
  "status": "ok",
  "data": {},
  "warnings": [],
  "errors": []
}
```

- `data`：本次接口的主输出
- `warnings`：可继续但需要提示用户的事项
- `errors`：结构化错误，失败时必须至少包含一条

## 模块契约

### 1. 岗位抓取

- 输入：页面上下文、登录态、分页位置、来源类型
- 输出：原始岗位列表、原始 JD、公司信息、抓取时间
- 入口：岗位页的“抓取”动作，未来也支持定时导入
- 失败：登录过期、页面结构变化、列表为空、详情缺失
- 最小输出字段：source_type、source_id、raw_payload、fetched_at、detail_url、page_cursor、raw_company_name、raw_title、raw_jd_text

### 2. 岗位识别

- 输入：抓取层原始数据、手动录入数据、外部导入数据
- 输出：统一岗位记录、关键词、结构化摘要、去重结果
- 入口：抓取后自动识别，也支持单条修正
- 失败：字段缺失、重复岗位、JD 不完整、城市和薪资不可解析
- 最小输出字段：job_id、title、company、city、salary、jd_text、keywords、summary、source_id、dedupe_key、status

### 3. 简历解析

- 输入：文件内容或文本内容
- 输出：结构化简历画像、技能、经历、目标岗位偏好
- 入口：简历实验室上传区
- 失败：格式不支持、提取失败、内容为空、解析不完整
- 最小输出字段：profile_id、name、title、skills、experience_blocks、project_blocks、education_blocks、raw_text、parse_status

### 4. 简历优化

- 输入：结构化简历画像 + 选中岗位 JD
- 输出：优化摘要、可编辑建议、关键词差距、改写提示
- 入口：简历实验室
- 失败：未选中岗位、JD 为空、简历未解析
- 最小输出字段：target_job_id、summary、bullets、matched_keywords、missing_keywords、edit_notes

### 5. 公司尽调

- 输入：岗位上下文、公司资料、AI 搜索结果、用户备注
- 输出：风险等级、行业前景、证据列表、结论、解释备注
- 入口：岗位卡片、岗位详情侧栏、排序页补全入口
- 失败：没有公司资料、AI 搜索失败、上下文不足、证据为空
- 最小输出字段：company_name、research_queries、research_sources、evidence_items、risk_level、industry_outlook、conclusion、editable_note

### 6. 互联网调研

- 输入：公司名、岗位标题、JD、用户备注、搜索范围
- 输出：原始搜索结果、证据条目、结构化摘要、可复用研究记录
- 入口：公司尽调按钮、尽调侧栏、排序页补全入口
- 失败：搜索超时、搜索为空、来源站点失效、证据重复
- 最小输出字段：research_id、company_name、queries、sources、source_snippets、evidence_items、summary、status

调研来源优先级：

1. 公司官网、招聘页、产品页、公告页
2. 主流新闻和融资报道
3. 技术社区、博客、开源仓库
4. 招聘平台上的公司介绍和 JD
5. 其他可验证公开网页

调研处理规则：

- 同一事实只保留一个主证据和若干辅助证据
- 明显过时或无法验证的内容要降低权重
- 搜索结果必须保留来源 URL、抓取时间、摘要和证据标签
- 同一公司多次调研要支持合并为一份可增量更新的研究记录
- 如果搜索结果不足，调研状态必须标记为 `partial`，不能伪装成完成

调研执行协议：

- 默认先并发基础词和验证词，再补拓展词
- 单次调研最多重试 2 次，超时后进入 `partial` 或 `failed`
- 每次查询都要记录 `query_group_id`、`backend`、`started_at`、`finished_at`
- 所有结果先进入研究缓存，再由尽调层挑选可用证据
- 调研层只负责生成研究记录，不直接输出最终结论

调研搜索词生成规则：

- 基础词：公司名 + 岗位标题 + JD 关键词
- 拓展词：公司名 + 融资 / 产品 / 技术栈 / 舆情 / 招聘
- 验证词：公司名 + 官网 / 招聘页 / 公告 / 新闻
- 排除重复：同义词和重复关键词只保留一个主词
- 限制范围：每次调研默认不超过 5 组查询，避免结果噪声过大

证据合并规则：

- 同一 URL 的重复抓取合并为一条证据
- 同一事实来自多个来源时，只保留可信度最高的主证据
- 证据必须包含 `source_type`、`source_url`、`captured_at`、`fact_type`、`confidence`
- 明显矛盾的证据不能自动覆盖，必须保留冲突备注
- 过期证据默认不删除，只降低权重

调研后端适配层：

- 输入：一组查询词、公司名、JD、搜索范围
- 输出：原始网页结果、标题、摘要、URL、时间戳、来源类型
- 责任：只做获取和归一化，不做最终判断
- 可替换实现：通用搜索引擎、网页阅读器、外部搜索 API、平台专用搜索工具
- 失败处理：返回空结果、错误码、超时原因和可重试标记

### 7. 评分与排序

- 输入：岗位记录、简历画像、尽调结果
- 输出：岗位分、公司分、行业分、综合分、排序位置、解释
- 入口：排序页
- 失败：缺少任一核心输入、分数无法归一化
- 最小输出字段：job_id、match_score、company_score、industry_score、total_score、rank_index、score_reason

评分建议默认权重：

- 岗位匹配分：40%
- 公司分：30%
- 行业分：20%
- 人工修正项：10%

如果某一项缺失，必须降级显示，并保留缺失原因，不得静默补零。

排序规则：

- 先按综合分降序
- 同分时优先公司分更高者
- 再同分时优先岗位匹配分更高者
- 仍同分时保留原始录入顺序，避免列表跳动

唯一真相源：

- `job` 的真相源是归一化岗位记录
- `resume` 的真相源是解析后的简历画像
- `research` 的真相源是研究记录
- `diligence` 的真相源是尽调结果
- `score` 的真相源是评分结果
- `send` 的真相源是发送回执和发送状态
- 页面展示内容只能从真相源派生，不能反向覆盖真相源

### 8. 话术与待发送箱

- 输入：岗位上下文、简历摘要、尽调结论、评分结果
- 输出：打招呼语草稿、人工编辑稿、待发送项、发送回执
- 入口：话术页、发送箱
- 失败：未生成草稿、未人工确认、发送失败
- 最小输出字段：job_id、draft_text、edited_text、confirm_status、send_status、receipt_id

## 页面结构

### 1. 工作台壳层

这是第一层，不再是单页面切换式“面板集合”，而是统一壳层：

- 左侧导航
- 顶部状态区：当前选中岗位、当前简历、当前流程阶段
- 中部主内容区
- 右侧详情抽屉或信息栏

壳层必须显示：

- 当前选中岗位
- 当前简历是否已解析
- 当前是否可以进入下一步

### 2. 简历实验室

用于上传、解析、修正和优化简历。

必须显示：

- 文件上传
- 解析结果
- 当前选中岗位的 JD 摘要
- 优化建议
- 错误提示

### 3. 岗位池

用于采集、筛选、查看和选择岗位。

必须显示：

- 岗位列表
- 岗位 JD
- 筛选条件
- 当前选中状态
- 进入简历优化的按钮

岗位池背后再分两层：

- 抓取层：负责登录、翻页、点选、拉取列表和详情
- 识别层：负责把抓回来的原始页面数据转成统一岗位记录，并补齐关键词、摘要和可比字段

### 4. 公司尽调与排序

用于查看尽调结果、行业前景和综合评分。

这一层必须支持从岗位池直接进入，也必须支持在排序页补做尽调。

### 5. 打招呼语与待发送箱

用于生成岗位定制话术、人工确认并发送。

## 数据流

```text
岗位抓取 -> 岗位识别/标准化 -> 岗位池 -> 选中目标岗位 -> JD 入库
简历上传 -> 解析 -> 结构化画像
画像 + JD -> 优化建议
公司信息输入 + 岗位上下文 -> 尽调
岗位 + 公司信息 + 简历画像 -> 尽调与评分
评分 + 优化稿 -> 话术草稿
话术草稿 -> 人工确认 -> 发送箱 -> 发送回执
```

## 状态机

### 岗位状态

- `raw`：仅有原始抓取内容
- `normalized`：已标准化
- `selected`：已被选中作为当前目标
- `diligenced`：已完成尽调
- `scored`：已完成评分
- `drafted`：已生成话术
- `queued`：已进入待发送
- `sent`：已发送完成

### 简历状态

- `empty`：尚未上传
- `parsed`：已解析
- `needs_review`：解析后待修正
- `optimized`：已生成优化建议

### 发送状态

- `drafted`
- `edited`
- `confirmed`
- `failed`
- `sent`

### 状态转移规则

| 当前状态 | 可转入状态 | 触发者 |
|---|---|---|
| `raw` | `normalized`, `failed` | 抓取/识别 |
| `normalized` | `selected`, `failed` | 用户选择 |
| `selected` | `diligenced`, `failed` | 用户发起尽调 |
| `diligenced` | `scored`, `failed` | 系统评分 |
| `scored` | `drafted`, `failed` | 系统生成话术 |
| `drafted` | `edited`, `queued`, `failed` | 用户编辑/加入待发送 |
| `edited` | `queued`, `failed` | 用户确认草稿 |
| `queued` | `confirmed`, `failed` | 用户最终确认 |
| `confirmed` | `sent`, `failed` | 发送器 |
| `sent` | 无 | 终态 |
| `empty` | `parsed`, `failed` | 简历解析 |
| `parsed` | `needs_review`, `optimized`, `failed` | 用户/系统 |
| `needs_review` | `optimized`, `failed` | 用户修正后 |

### 严格门控规则

- 没有 `selected` 岗位，不得进入尽调、评分、话术生成和发送箱
- `research` 只有 `ready` 或明确接受的 `partial` 才能进入尽调
- 没有 `parsed` 简历，不得进入优化和评分
- 没有 `diligenced` 结果，不得进入评分
- 没有 `scored` 结果，不得进入话术生成
- 没有 `confirmed` 草稿，不得进入发送

### 研究状态

- `pending`：尚未发起调研
- `running`：AI 正在搜索互联网
- `partial`：只拿到部分可用证据
- `ready`：研究结果可供尽调
- `failed`：搜索失败但保留查询和上下文

### 研究状态转移规则

- `pending` -> `running`：用户发起尽调或系统补全
- `running` -> `partial`：部分来源失败但已有可用证据
- `running` -> `ready`：证据足够，可进入尽调
- `running` -> `failed`：无可用结果或搜索异常
- `partial` -> `ready`：补搜后证据完整
- `failed` -> `running`：用户重试

### 失败回滚规则

- 抓取失败：保留原始请求和页面上下文，可重试抓取
- 识别失败：保留 raw_payload，可重试标准化
- 研究失败：保留查询词和失败来源，可重新搜索
- 尽调失败：保留研究证据和用户备注，可重新归纳
- 评分失败：保留尽调结果和简历画像，可重新计算
- 话术失败：保留评分结果和简历摘要，可重新生成
- 发送失败：保留草稿和确认记录，可重试发送，但不得重复提交成功回执

### 研究证据结构

- `source_type`
- `source_url`
- `source_title`
- `captured_at`
- `fact_type`
- `fact_summary`
- `confidence`
- `note`

## UI 重构规则

1. 不使用复杂的营销式首页。
2. 不把页面节包成卡片再套卡片。
3. 每个模块只保留必要控件。
4. 所有关键动作都要有明显状态反馈。
5. 空状态要告诉用户下一步做什么。
6. 当前选中岗位要在全局可见。
7. 当前选中岗位的 JD 必须在简历模块可见。
8. 在没有选中岗位前，简历优化必须被阻止。

## 页面空态

### 简历页

- 尚未上传简历：提示上传
- 已上传但未解析：显示解析中
- 已解析但无选中岗位：提示先去岗位页选目标
- 已解析且选中岗位但优化失败：显示错误原因和重试按钮
- 推荐文案：`先上传简历，再选择一个岗位作为优化目标。`
- 错误文案：`简历解析失败，请检查文件格式后重试。`

### 岗位页

- 没有岗位：提示导入或抓取
- 抓取结果为空：提示调整筛选或换来源
- 有岗位但重复：提示已去重
- 选中岗位：显示当前目标和下一步
- 推荐文案：`先抓取岗位，或者导入已有列表。`
- 错误文案：`岗位抓取失败，请稍后重试或调整筛选条件。`

### 研究/尽调页

- 未发起研究：提示先点尽调
- 研究进行中：显示 running
- 研究部分完成：明确显示 partial 和缺失来源
- 研究失败：显示重试入口和失败原因
- 推荐文案：`先对公司做一次互联网调研，再进入尽调。`
- 错误文案：`互联网调研暂时失败，请重试或更换搜索词。`

### 排序页

- 没有尽调：提示先研究并尽调
- 没有评分：提示先完成简历和研究
- 分数并列：显示排序规则说明
- 推荐文案：`完成研究和尽调后，这里会按综合分排序。`
- 错误文案：`当前缺少评分输入，请先完成简历、研究和尽调。`

### 话术页

- 没有评分或尽调：提示先完成前置步骤
- 没有草稿：提示生成话术
- 草稿失败：显示错误和重试
- 推荐文案：`先完成评分，再生成适合这个岗位的话术。`
- 错误文案：`话术生成失败，请检查前置数据后重试。`

### 发送箱

- 没有确认草稿：提示先编辑并确认
- 发送中：显示发送中状态
- 发送失败：显示失败原因和重试
- 已发送：显示回执和终态
- 推荐文案：`确认前先检查草稿，确认后只在这里发送。`
- 错误文案：`发送失败，请稍后重试，已保留当前草稿。`

## 按钮规则

### 简历页

- `上传简历`：始终可点
- `生成优化建议`：仅在简历已解析且有选中岗位时可点
- `重试解析`：仅在解析失败时可点

### 岗位页

- `抓取岗位`：始终可点
- `导入岗位`：始终可点
- `选为目标`：仅对未选中的岗位可点
- `查看尽调`：仅对已选中岗位可点

### 研究/尽调页

- `发起研究`：有公司名和岗位上下文时可点
- `重新研究`：研究失败或 partial 时可点
- `进入尽调`：研究为 ready 或已接受 partial 时可点

### 排序页

- `重新评分`：有简历、岗位和尽调结果时可点
- `查看解释`：始终可点

### 话术页

- `生成草稿`：评分完成后可点
- `编辑草稿`：草稿存在时可点

### 发送箱

- `确认发送`：草稿已编辑且状态允许时可点
- `重试发送`：发送失败时可点

## 复用策略

### 可以复用的思路

- JobPilot 的本地工作台和工具调用结构
- JobPilot 的逐条应用修改、guardrail、JD 匹配
- Align-Resume 的 truthful rewriting、评分与缺口分析
- CVTailor 的导入、ATS 风格和导出体验

### 不直接复用的部分

- 任何偏企业招聘端的业务结构
- 任何依赖过重、需要完整后端服务集群的设计
- 任何会把 UI 做成演示页的装饰性布局

## 开发阶段

### 阶段 0：工作台重构

先把壳层、导航、状态区、当前选中岗位和当前简历状态做好。

完成标准：

- 打开页面就能看懂现在在做什么
- 当前目标岗位永远可见
- 简历和岗位状态不会互相丢失

### 阶段 1：简历模块重做

上传、解析、修正、优化一条链路打通，优化必须读取选中岗位的 JD。

完成标准：

- 上传简历能看到结构化解析
- 选中岗位后可直接生成优化建议
- 没有选中岗位时不能优化

### 阶段 2：岗位模块重做

岗位抓取、识别、筛选、选择、JD 展示、状态同步。

完成标准：

- 每个岗位有完整 JD 和结构化摘要
- 能看出岗位是从哪里抓回来的
- 抓取后的原始内容会被识别层标准化
- 选择岗位后全局同步
- 岗位页能明确告诉用户“下一步做什么”

### 阶段 3：尽调与排序

把公司风险、行业前景和综合评分整合成排序结果。

完成标准：

- 从岗位池或排序页都能进入尽调
- 尽调默认通过 AI 搜索互联网获得公司资料
- 尽调结果能解释来源，不只是一个分数
- 没有尽调时，排序页会提示先补尽调
- 尽调与评分能复用同一份岗位上下文

## 仍然缺的模块

1. 岗位来源的统一入口与去重规则。
2. AI 搜索互联网的结果标准化与证据抽取层。
3. 尽调结果的可编辑区，允许人工修正。
4. 排序的解释层，说明为什么这个岗位排前面。
5. 全局状态的持久化策略，避免刷新后丢失当前目标。
6. 每个模块的空态、错态、半完成态文案。
7. 针对每个阶段的人工窗口测试清单。
8. 每个模块的输入输出 schema 草案。
9. 岗位、简历、尽调、话术的状态流转规则。
10. 失败后的重试和回滚约定。

## 人工测试清单

### 阶段 0

- 进入应用后能看到当前目标岗位状态
- 切换页面后选中岗位不丢失
- 没选岗位时简历优化入口会阻止继续

### 阶段 1

- 上传简历能看到解析结果
- 更换岗位后优化建议会变化
- 没有解析结果时不能进入优化

### 阶段 2

- 能看到岗位来源和结构化摘要
- 同一岗位重复导入不会出现两条
- 选中岗位后简历页同步显示

### 阶段 3

- 从岗位页能进入尽调
- 尽调结果能看到 AI 搜索来的证据
- 排序页能解释综合分来源

### 阶段 4

- 草稿可编辑
- 确认前不能发送
- 已发送状态不会重复提交
- 重复点击确认不会生成第二条发送回执

### 异常场景

- 搜索超时后可重试且保留查询词
- 调研只有部分证据时，尽调页会明确提示证据不足
- 重复导入同一岗位时只保留一条归一化记录
- 简历未解析时，优化按钮保持阻断状态
- 发送失败时保留草稿和确认状态，不清空编辑内容

### 阶段 4：话术与待发送箱

生成岗位定制话术，人工确认后再进入发送。

## 验收标准

- UI 先重构成清晰的工作台，不再是失控面板。
- 简历优化从选中岗位的 JD 读取目标，不再手填岗位名。
- 岗位选择会驱动简历、评分和话术模块。
- 每个模块都有明确空态、加载态、错误态。
- 发送动作必须经过人工确认。
