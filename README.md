# boss 求职助手

boss 求职助手是一款面向桌面端的本地求职工作台，围绕 BOSS 直聘岗位管理提供简历、JD、公司尽调、岗位排序和沟通管理能力。

应用只面向桌面端使用，业务数据和运行日志默认保存在本机。

## 功能

### 仪表盘

- 查看岗位、简历、尽调、排序和打招呼的整体进度。
- 查看运行任务、系统健康状态和待处理事项。
- 管理失败任务，支持重试、删除和清空。
- 管理 AI 版本记录，支持刷新、折叠、删除和清空。
- 根据流程状态进入对应功能页面。

### 简历

- 上传和解析 PDF 简历。
- 保存简历资料和简历版本。
- 根据目标岗位 JD 进行 AI 评估与优化。
- 生成、预览和下载 PDF 简历。
- 查看简历优化记录和 AI 对话记录。

### 岗位

- 检查 BOSS 登录状态。
- 按关键词、城市和岗位筛选条件抓取岗位。
- 按岗位名称和公司名称进行去重。
- 导入、筛选、批量选择、删除和导出岗位。
- 管理岗位标签、岗位状态、搜索预设和企业黑名单。
- 查看岗位池质量、重复岗位、疑似过期岗位和抓取批次。
- 获取岗位详情 JD，默认跳过已有详情 JD。
- 支持重新抓取 JD，并在抓取过程中同步岗位结果。
- 黑名单岗位不进入正常岗位处理，也不计入缺少 JD 统计。
- 自动化任务结束后关闭相关浏览器进程。

### 公司尽调

- 对岗位 JD 执行 AI 分析。
- 获取和整理公司工商、招聘和网络搜索信息。
- 生成公司尽调报告、风险提示和行动建议。
- 支持独立的一键 JD 分析和一键公司尽调；两项批量任务可并行执行并分别展示进度。
- 支持重新 JD 分析、重新公司尽调、备注、对话和报告导出。

### 排序

- 根据简历匹配度、JD 要求、公司尽调和用户偏好生成岗位排序。
- 支持权重设置和排序结果复核。
- 展示推荐理由、风险信息和下一步建议。
- 支持排序结果导出。

### 打招呼

- 根据岗位和 JD 生成打招呼话术。
- 支持单个或批量生成、重新生成、复制和校验。
- 自动过滤已经打过招呼的岗位。
- 支持岗位定制简历、AI 简历优化、预览和下载。
- 发送前检查登录状态、岗位详情、话术和页面状态。
- 支持发送记录、HR 回复和后续跟进。
- 遇到登录失效、验证码、风控或页面异常时停止任务并记录结果。

### 设置与帮助

- 配置 AI Provider、搜索服务和工商信息服务。
- 管理用户偏好、备份、恢复和系统维护。
- 一键清空本地数据包。
- 查看功能说明、操作流程和常见问题。

## 技术组成

- 前端：React、TypeScript、Vite。
- 前端测试：Vitest、Testing Library、Playwright。
- 后端：FastAPI、Pydantic、Python 3.9+。
- 本地存储：JSON、SQLite 和本地文件。
- 桌面容器：Electron、electron-builder。
- 浏览器自动化：Playwright 和本地 Chromium。
- 文件处理：PDF 解析、PDF 生成和简历文件管理。

## 环境要求

- macOS、Windows 或 Linux 桌面系统。
- Node.js。
- pnpm 11。
- Python 3.9 或更高版本。
- 可安装 Python 后端依赖的本地构建环境。

## 本地启动

在项目根目录执行：

```bash
./start.sh
```

启动后访问：

```text
http://127.0.0.1:5173
```

启动脚本会在前端构建产物不存在时自动安装前端依赖并构建前端。

手动安装和构建：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm build

cd ../backend
python3 -m pip install -e .
```

## 常用命令

```bash
# 前端类型检查
pnpm --dir frontend typecheck

# 前端单元测试和回归测试
pnpm --dir frontend test:run

# 前端生产构建
pnpm --dir frontend build

# 前端端到端测试
pnpm --dir frontend test:e2e

# 后端测试
pytest -q backend/tests

# 发布检查
python3 scripts/release_check.py
```

## 桌面端打包

使用完整桌面构建脚本：

```bash
python3 scripts/build_desktop.py mac
```

可用目标：

```text
mac       macOS 目录包
mac-dmg   macOS DMG 安装包
win       Windows NSIS 安装包
linux     Linux AppImage 和 deb
dir       目录包
```

macOS ARM64 安装包：

```bash
python3 scripts/build_desktop.py mac-dmg arm64
```

打包结果位于：

```text
release/desktop/
```

## 数据目录

开发模式默认使用：

```text
~/.boss-auto-apply
```

桌面安装包使用 Electron 用户数据目录下的：

```text
data/
```

本地数据包括：

- 岗位池和岗位状态。
- 简历资料、简历文件和优化版本。
- JD 分析、公司尽调和排序结果。
- 打招呼草稿、发送记录和回复记录。
- 搜索预设、企业黑名单和用户设置。
- 浏览器登录态、任务数据和运行日志。

## 运行日志

日志位于数据目录的 `logs/`：

```text
runtime.log
chrome.log
desktop.log
backend-stdout.log
backend-stderr.log
events.jsonl
api_calls.jsonl
```

日志用于排查后端启动、浏览器自动化、岗位抓取、JD 获取、任务失败和进程退出问题。

日志和业务数据可能包含简历、岗位、账号状态或其他个人信息，不应直接公开或上传到公共位置。

## 数据清理

设置页提供“一键清空本地数据包”。清理范围包括本地业务数据、上传文件、浏览器登录态、日志和已保存的 API 配置。

该操作不可撤销，执行前应先导出需要保留的数据。

## 安全说明

- 服务默认只监听 `127.0.0.1`。
- BOSS 操作使用正常页面流程，不绕过登录、验证码或平台风控。
- 真实发送前需要用户确认。
- API 配置在本地加密保存。
- 完整备份可能包含个人简历、岗位和日志，应保存在可信位置。
- 对外排查时优先使用脱敏备份。

详细说明见 [docs/SECURITY.md](docs/SECURITY.md)。

## 项目结构

```text
.
├── backend/       FastAPI 后端、业务服务、数据模型和后端测试
├── frontend/      React 页面、组件、状态、API 和前端测试
├── desktop/       Electron 主进程
├── build/         桌面端图标资源
├── scripts/       启动、构建和发布检查脚本
├── docs/          项目安全文档
├── start.sh       本地启动入口
└── package.json   桌面端配置
```

## 使用流程

1. 在设置中配置所需服务。
2. 上传并检查简历。
3. 登录 BOSS 并抓取岗位。
4. 筛选岗位并获取 JD。
5. 执行 JD 分析和公司尽调。
6. 生成岗位排序。
7. 生成岗位话术和定制简历。
8. 小批量确认发送并跟踪反馈。
