# boss 求职助手

本地优先的桌面求职工作台。它将岗位收集、岗位筛选、JD 与公司尽调、AI 匹配排序、沟通话术、BOSS 页面辅助发送和求职 CRM 串成一条可复盘的流程。

业务数据、登录态与诊断日志默认仅保存在本机。应用不会绕过 BOSS 的登录、验证码或风控机制；自动发送前会执行登录与页面预检，遇到风险信号会停止任务并留下记录。


## 核心能力

### 以「已选岗位」驱动流程

- 岗位池支持抓取、导入、搜索、标签、状态管理、去重、导出，以及企业黑名单维护。
- 可按抓取批次查看结果；批次详情默认收起，永久删除只影响该批次的岗位，不会误删其他批次。
- 用户从岗位页筛选、勾选后，选择会持久化并带入尽调、排序、打招呼和仪表盘流程引导。
- 黑名单、下架岗位会从后续流程及对应统计中排除。

### 尽调与岗位排序

- 支持独立执行一键 JD 分析与一键公司尽调，并分别展示进度和结果。
- 汇总 JD 要求、公司信息、风险、AI 反馈与行动建议，支持重新分析、备注、对话和报告导出。
- 基于简历、JD、尽调和偏好生成推荐排序；可按推荐分筛选，再将勾选岗位带入打招呼。
- AI 匹配调用会自动重试；失败结果不会混入正式排序，可用“继续排序”只重试未完成岗位。

### 打招呼与跟进

- 为选中的岗位生成、校验、复制和重新生成个性化话术，支持岗位定制简历与 AI 简历优化。
- 支持人工确认与受控的真实自动发送。开始前会检查登录有效性、岗位详情、话术、页面可用性和安全阈值。
- 已发送、跳过、失败会被分别记录；跳过不会被任务中心判定为失败，跳过原因可清空。
- 提供发送记录、HR 回复、后续跟进和 CRM 看板，便于复盘触达效果。

### 仪表盘、任务与维护

- 仪表盘提供流程引导、全流程状态、数据质量体检、任务中心、系统健康、AI 版本记录和策略复盘。
- 数据质量、AI 反馈、风险岗位等卡片可跳转至岗位页并自动带入对应筛选条件。
- 仪表盘同时展示全库概览与“已选岗位”口径；卡片会标示统计范围，避免混淆。
- 支持 AI 服务配置、登录状态检测、备份恢复、日志查看和本地数据清理。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 桌面端 | Electron、electron-builder |
| 前端 | React 19、TypeScript、Vite |
| 后端 | FastAPI、Pydantic、Python 3.9+ |
| 自动化 | Playwright、随桌面端打包的 Chromium |
| 测试 | Vitest、Testing Library、Playwright、pytest |
| 本地存储 | JSON、SQLite、本地文件 |

## 快速开始

### 环境要求

- Node.js 与 `pnpm`（项目使用 pnpm 11）
- Python 3.9 或更高版本
- macOS、Windows 或 Linux 桌面环境

### 开发模式启动

在项目根目录运行：

```bash
./start.sh
```

首次运行时，脚本会在前端构建产物缺失时安装前端依赖并构建。服务默认监听 `http://127.0.0.1:5173`。

如需手动准备依赖：

```bash
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
python3 -m pip install -e ./backend
```

## 使用流程

1. 在“设置”中配置 AI 服务，并按需配置搜索或企业信息服务。
2. 上传简历、补充偏好并检查登录状态。
3. 在“岗位”页抓取或导入岗位，筛选后勾选感兴趣的岗位。
4. 获取 JD，执行 JD 分析和公司尽调；处理风险或 AI 反馈。
5. 在“排序”页生成推荐，按得分筛选并选择准备沟通的岗位。
6. 进入“打招呼”页生成话术，先人工确认或小批量灰度验证，再决定是否开启自动发送。
7. 在仪表盘和 CRM 看板中查看任务、回复、跟进与质量问题。

## 常用命令

```bash
# 前端：类型检查、单元/回归测试、生产构建
pnpm --dir frontend typecheck
pnpm --dir frontend test:run
pnpm --dir frontend build

# 前端端到端冒烟测试
pnpm --dir frontend test:e2e

# 前端完整校验（类型检查 + 测试 + 构建）
pnpm --dir frontend validate

# 后端测试
PYTHONPATH=backend python3 -m pytest backend/tests -q

# 发布前检查
python3 scripts/release_check.py
```

## 桌面端打包

桌面构建会依次构建前端、用 PyInstaller 打包后端、准备 Playwright Chromium，并由 Electron Builder 生成安装包。

```bash
# 当前平台默认产物
pnpm desktop:build

# macOS DMG（Apple Silicon）
pnpm desktop:dist

# 或直接指定平台与架构
python3 scripts/build_desktop.py mac-dmg arm64
python3 scripts/build_desktop.py win x64
python3 scripts/build_desktop.py linux x64
```

产物位于 `release/desktop/`。打包过程会下载所需 Chromium；请确保网络和磁盘空间充足。

## 本地数据与日志

开发模式的数据目录默认为：

```text
~/.boss-auto-apply/
```

安装版由 Electron 在用户数据目录下创建 `data/`，并通过 `BOSS_WORKBENCH_DATA_DIR` 传递给后端。目录包括岗位与工作流状态、简历和导出文件、排序与话术结果、浏览器登录态、设置、SQLite 数据库和日志。

常用诊断日志在 `logs/` 下：

```text
runtime.log
chrome.log
desktop.log
backend-stdout.log
backend-stderr.log
events.jsonl
api_calls.jsonl
```

这些文件可能含有岗位、简历、账号状态或服务调用信息。排查问题时请先脱敏，切勿直接上传到公共位置。

## 安全与使用边界

- 服务只监听本机回环地址 `127.0.0.1`。
- 登录、验证码、风控和平台限制由用户在正常页面流程中处理；应用不会尝试绕过。
- 自动发送属于高风险操作：请先确认话术、岗位选择和登录状态，建议从少量岗位开始。
- “清空本地数据包”会清除本地业务数据、上传文件、登录态、日志和已保存配置，操作不可撤销；请先导出需要保留的内容。

更多安全细节参见 [docs/SECURITY.md](docs/SECURITY.md)。

新人可按 [API 配置指南](docs/API_CONFIGURATION_GUIDE.md) 完成 DeepSeek、百度千帆智能搜索和腾讯云市场工商 API 的注册、订阅、密钥创建与应用内测试。

## 参考项目与第三方声明

### 参考实现

- [eatmoreduck/boss-zhipin-scraper](https://github.com/eatmoreduck/boss-zhipin-scraper)（MIT）：`backend/app/services/boss_scraper.py` 参考了其通过 Chrome DevTools Protocol（CDP）复用已登录浏览器会话的实现思路。

该参考项目**不是本应用的运行时依赖**：本项目未导入、未打包、未直接复制该仓库的源码；岗位抓取服务由本项目独立实现。若未来引入或复制第三方源码，将在对应文件保留来源、许可和修改说明，并同步更新本节。

### 使用的开源依赖

本项目通过包管理器使用以下主要开源项目，具体版本和完整依赖树以 `package.json`、`frontend/package.json` 与 `backend/pyproject.toml` 为准：

- [Electron](https://github.com/electron/electron) 与 [electron-builder](https://github.com/electron-userland/electron-builder)
- [React](https://github.com/react/react)、[Vite](https://github.com/vitejs/vite) 与 [TypeScript](https://github.com/microsoft/TypeScript)
- [FastAPI](https://github.com/fastapi/fastapi)、[Pydantic](https://github.com/pydantic/pydantic) 与 [Uvicorn](https://github.com/Kludex/uvicorn)
- [Playwright](https://github.com/microsoft/playwright)

上述依赖均按照各自许可证使用；发行或二次分发时，请同时遵守其许可证与 BOSS 直聘等相关平台的规则。

## 项目结构

```text
.
├── backend/        FastAPI 路由、业务服务、数据模型与 pytest 测试
├── frontend/       React 页面、组件、状态、API 与前端测试
├── desktop/        Electron 主进程与桌面运行时逻辑
├── build/          桌面应用图标资源
├── scripts/        启动预检、打包和发布检查脚本
├── docs/           安全文档等项目说明
├── start.sh        本地开发启动入口
└── package.json    Electron Builder 与桌面端脚本
```
