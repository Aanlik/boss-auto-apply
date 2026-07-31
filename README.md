# boss 求职助手

版本：`1.0.2`

`boss 求职助手` 是一个面向桌面端的本地求职工作台，用于管理 BOSS 直聘岗位、补全 JD、分析公司、排序岗位、优化简历和处理沟通流程。应用运行在本机，业务数据默认保存在本地，不提供移动端界面。

## 当前能力

### 工作台

- 查看岗位、简历、尽调、排序和打招呼的整体进度。
- 查看任务状态、失败任务和运行健康状态。
- 重试、删除和清空失败任务。
- 查看 AI 版本记录，并支持刷新、折叠、删除和清空。

### 简历

- 上传并解析 PDF 简历。
- 保存简历内容和多个优化版本。
- 根据目标岗位 JD 进行 AI 优化。
- 预览、生成和下载 PDF 简历。
- 查看优化结果、版本记录和相关聊天记录。

### 岗位

- 检查 BOSS 登录状态并执行岗位抓取。
- 按岗位名称、城市和筛选条件抓取岗位。
- 以“岗位名称 + 公司名称”进行抓取去重，避免重复抓取覆盖已有岗位。
- 导入、筛选、标记、删除、导出和批量管理岗位。
- 管理岗位标签、状态、企业黑名单和搜索预设。
- 查看岗位池质量、重复岗位、疑似过期岗位和抓取批次。
- 获取 JD 时默认跳过已有详情 JD，支持重新抓取 JD。
- 黑名单岗位不计入“缺少 JD”统计和 JD 待办数量。
- JD 抓取期间实时刷新岗位结果，并在任务结束后关闭自动化浏览器。

### 公司尽调与排序

- 对岗位执行 JD 分析和公司尽调。
- 根据岗位、公司、JD、简历匹配度和用户偏好生成排序。
- 支持重新分析、重新尽调、调整权重和查看排序依据。
- 保存尽调与排序结果，并支持导出。

### 打招呼

- 按岗位生成和校验打招呼话术。
- 支持批量选择、复制、重新生成和发送前确认。
- 自动过滤已经打过招呼的岗位。
- 支持 AI 优化简历、简历预览、模板和发送记录。
- 发送流程会检查登录状态、岗位详情、话术和页面状态。
- 遇到登录失效、验证码、风控或页面异常时停止并记录任务结果。

### 设置与帮助

- 配置 AI Provider、百度搜索和工商信息服务。
- 管理用户偏好、备份、恢复和维护检查。
- 一键清空本地数据包，包括岗位、简历、附件、尽调、排序、打招呼记录、登录态、日志和 API 配置。
- 查看使用流程、模块说明和常见问题。

## 技术组成

- 前端：React、TypeScript、Vite、Vitest、Playwright。
- 后端：FastAPI、Pydantic、Python 3.9+。
- 存储：本地 JSON 与 SQLite。
- 桌面端：Electron、electron-builder。
- 浏览器自动化：Playwright 和本地 Chromium 运行时。
- 文档与文件：PDF 解析、PDF 生成和简历文件管理。

## 开发环境

需要安装：

- macOS、Windows 或 Linux 桌面环境。
- Node.js 与 pnpm 11。
- Python 3.9 或更高版本。
- 后端依赖安装所需的 Python 构建环境。

## 本地启动

在项目根目录执行：

```bash
./start.sh
```

首次启动前，如果前端尚未构建，启动脚本会自动安装前端依赖并构建页面。启动后访问：

```text
http://127.0.0.1:5173
```

也可以分别构建前端和安装后端依赖：

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

# 前端单元与回归测试
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

构建完整桌面运行时并生成当前平台安装包：

```bash
python3 scripts/build_desktop.py mac
```

常用目标：

```text
mac       macOS 目录包
mac-dmg   macOS DMG 安装包
win       Windows NSIS 安装包
linux     Linux AppImage 与 deb
dir       当前平台目录包
```

macOS ARM64 DMG 也可以使用：

```bash
python3 scripts/build_desktop.py mac-dmg arm64
```

构建产物位于 `release/desktop/`。未配置代码签名时，macOS 可能提示需要在系统设置中允许打开应用。

## 本地数据与日志

开发模式默认数据目录为：

```text
~/.boss-auto-apply
```

桌面安装包使用 Electron 用户数据目录下的 `data/`。其中包括岗位、简历、尽调、排序、打招呼记录、配置、浏览器登录态和日志。

运行日志位于数据目录的 `logs/`：

```text
runtime.log
chrome.log
desktop.log
backend-stdout.log
backend-stderr.log
events.jsonl
api_calls.jsonl
```

日志用于定位抓取中断、JD 失败、浏览器关闭和后端退出原因。日志和本地数据可能包含个人信息，不应直接上传到公共位置。

## 安全边界

- 默认只监听 `127.0.0.1`。
- BOSS 操作通过正常页面流程执行，不绕过登录、验证码或平台风控。
- 自动发送前需要用户确认，并保留任务记录。
- API 配置在本地加密保存，密钥文件和业务数据不应提交到 Git。
- 完整备份可能包含简历、岗位和日志；对外排查时应优先使用脱敏备份。
- 清空本地数据包是不可逆操作，执行前应确认不再需要当前数据。

详细安全说明见 [docs/SECURITY.md](docs/SECURITY.md)。

## 项目结构

```text
.
├── backend/       FastAPI 服务、业务逻辑、数据模型和后端测试
├── frontend/      React 页面、组件、状态、API 和前端测试
├── desktop/       Electron 主进程
├── build/         桌面端图标资源
├── scripts/       启动检查、发布检查和桌面构建脚本
├── docs/          安全说明
├── start.sh       本地开发启动入口
└── package.json   Electron 打包配置
```

## 推荐使用流程

1. 在“设置”中配置需要使用的服务。
2. 在“简历”中上传并检查简历。
3. 在“岗位”中登录 BOSS，抓取并筛选岗位。
4. 获取 JD，处理重复岗位、过期岗位和黑名单岗位。
5. 执行 JD 分析与公司尽调。
6. 生成岗位排序并确认优先级。
7. 在“打招呼”中生成话术和岗位定制简历。
8. 小批量确认发送，并在工作台跟进结果。
