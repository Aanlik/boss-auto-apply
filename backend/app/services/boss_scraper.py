"""
Boss 直聘岗位抓取服务 — CDP + API 模式
独立实现，参考 eatmoreduck/boss-zhipin-scraper 的 CDP 抓取思路，无运行时依赖：
  - 连接系统 Chrome 的 CDP 调试端口
  - 在页面中执行 JS 调 Boss 内部搜索 API
  - API 返回明文薪资数据，绕过字体反爬

参考边界：
  - 本模块不 import、不安装、不调用 boss-scraper-ref 目录或第三方项目包
  - boss-scraper-ref 仅作为本地归档参考，不属于应用运行路径

关键设计：
  1. flatten attach 后不显式调用 Page.enable / Runtime.enable
     （显式 enable 会订阅大量生命周期事件，send() 消费它们会破坏页面状态）
  2. 使用 Page.navigate + sleep 等待 SPA 页面加载
  3. API URL 使用完整绝对路径（因页面可能从 about:blank 开始）
"""
import json
import logging
import os
import random
import subprocess
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
import websocket

from app.services.city_codes import load_city_codes, resolve_city_code
from app.services import workflow_persistence

logger = logging.getLogger("boss_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOSS] %(message)s", datefmt="%H:%M:%S")

# ——— 配置 ———
DATA_DIR = workflow_persistence.DATA_DIR
CDP_PROFILE = str(DATA_DIR / "chrome_profile")
CDP_PORT = 9222
API_SEARCH = "/wapi/zpgeek/search/joblist.json"
API_BASE = "https://www.zhipin.com"
_detail_enrich_running = False

CITY_CODES = load_city_codes()

API_JS_TEMPLATE = """(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '__API_URL__', false);
    xhr.send();
    if (xhr.status !== 200) return JSON.stringify({httpStatus: xhr.status, body: xhr.responseText});
    var data = JSON.parse(xhr.responseText);
    var jobs = (data.zpData || {}).jobList || [];
    return JSON.stringify(jobs.map(function(j) {
        return {
            title: j.jobName || '',
            salary: j.salaryDesc || '',
            location: (j.cityName||'') + ' · ' + (j.areaDistrict||''),
            company: j.brandName || '',
            boss_name: j.bossTitle || '',
            boss_active: j.activeTimeDesc || (j.bossOnline ? '在线' : ''),
            scale: j.brandScaleName || '',
            stage: j.brandStageName || '',
            industry: j.brandIndustry || '',
            labels: (j.jobLabels||[]).join(' | '),
            skills: (j.skills||[]).join(' | '),
            exp: j.jobExperience || '',
            degree: j.jobDegree || '',
            encrypt_job_id: j.encryptJobId || '',
            encrypt_brand_id: j.encryptBrandId || '',
            job_link: j.encryptJobId ? 'https://www.zhipin.com/job_detail/'+j.encryptJobId+'.html' : '',
            welfare: (j.welfareList||[]).join(' | '),
        };
    }));
})()"""

PROBE_JS = """(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '__PROBE_URL__', false);
    xhr.send();
    return JSON.stringify({httpStatus: xhr.status, body: xhr.responseText});
})()"""

GREETING_SEND_JS_TEMPLATE = r"""(async function(){
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    const bodyText = (document.body && document.body.innerText || '').toLowerCase();
    if (bodyText.includes('登录') && (location.href.includes('/web/user') || bodyText.includes('微信扫码'))) {
        return JSON.stringify({ok:false, status:'blocked', failureCode:'not_logged_in', message:'未登录或登录页可见'});
    }
    if (['验证码','滑块','拼图','captcha','verify','操作太频繁','稍后再试','账号异常','限制使用'].some(t => bodyText.includes(t.toLowerCase()))) {
        return JSON.stringify({ok:false, status:'blocked', failureCode:'risk_control', message:'检测到验证码、风控或账号异常提示'});
    }

    function visible(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    }
    function nearestActionable(el) {
        if (!el) return null;
        return el.closest('button,a,[role="button"],.btn,.btn-startchat,.start-chat,.op-btn,.btn-greet') || el;
    }
    function actionableByText(selectors, texts) {
        const nodes = Array.from(document.querySelectorAll(selectors));
        const candidates = nodes
            .filter(visible)
            .map(el => ({source: el, target: nearestActionable(el)}))
            .filter(item => item.target && visible(item.target))
            .filter(item => {
                const text = (item.target.innerText || item.target.textContent || item.source.innerText || item.source.textContent || '').trim();
                return texts.some(t => text.includes(t));
            });
        candidates.sort((a, b) => {
            const ar = a.target.getBoundingClientRect();
            const br = b.target.getBoundingClientRect();
            const aArea = ar.width * ar.height;
            const bArea = br.width * br.height;
            const aNative = /^(A|BUTTON)$/.test(a.target.tagName) ? 0 : 1;
            const bNative = /^(A|BUTTON)$/.test(b.target.tagName) ? 0 : 1;
            return aNative - bNative || aArea - bArea;
        });
        return candidates[0] ? candidates[0].target : null;
    }
    function clickElement(el) {
        const target = nearestActionable(el);
        if (!target || !visible(target)) return false;
        target.scrollIntoView({block:'center', inline:'center'});
        ['pointerdown','mousedown','mouseup','click'].forEach(type => {
            target.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, view:window}));
        });
        if (typeof target.click === 'function') target.click();
        return true;
    }
    async function waitFor(fn, timeoutMs, intervalMs) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            const value = fn();
            if (value) return value;
            await sleep(intervalMs || 250);
        }
        return null;
    }
    function chatInput() {
        const selectors = [
            '.startchat-dialog textarea',
            '.startchat-dialog .input-area',
            '.dialog-wrap textarea',
            '.dialog-wrap [contenteditable="true"]',
            'textarea.input-area',
            '#chat-input',
            '[class*="chat-input"]',
            '[contenteditable="true"]',
            'textarea'
        ].join(',');
        const inputs = Array.from(document.querySelectorAll(selectors))
            .filter(visible)
            .filter(el => !String(el.className || '').includes('ipt-search'))
            .filter(el => !String(el.getAttribute('type') || '').toLowerCase().includes('search'));
        inputs.sort((a, b) => {
            const aDialog = a.closest('.startchat-dialog,.dialog-wrap') ? 0 : 1;
            const bDialog = b.closest('.startchat-dialog,.dialog-wrap') ? 0 : 1;
            const aTextarea = a.tagName === 'TEXTAREA' ? 0 : 1;
            const bTextarea = b.tagName === 'TEXTAREA' ? 0 : 1;
            return aDialog - bDialog || aTextarea - bTextarea;
        });
        return inputs[0] || null;
    }
    let chatButton = actionableByText('button,a,span,div', ['立即沟通','立即投递','投递简历','继续沟通']);
    if (!chatButton) {
        return JSON.stringify({ok:false, status:'failed', failureCode:'button_not_found', message:'未找到立即沟通按钮'});
    }
    if (!clickElement(chatButton)) {
        return JSON.stringify({ok:false, status:'failed', failureCode:'button_click_failed', message:'立即沟通按钮不可点击'});
    }
    await sleep(1200);

    let input = await waitFor(chatInput, 8000, 300);
    if (!input) {
        return JSON.stringify({ok:false, status:'failed', failureCode:'input_not_found', message:'未找到聊天输入框'});
    }

    const message = __MESSAGE_JSON__;
    input.focus();
    if ('value' in input) {
        const proto = input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        if (setter) setter.call(input, message);
        else input.value = message;
        input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:message}));
        input.dispatchEvent(new Event('input', {bubbles:true}));
        input.dispatchEvent(new Event('change', {bubbles:true}));
    } else {
        input.textContent = '';
        document.execCommand('insertText', false, message);
        input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:message}));
    }
    await sleep(800);

    let sendButton = await waitFor(() => actionableByText('button,span,div,a,[role="button"]', ['发送']), 5000, 250);
    if (!sendButton) {
        return JSON.stringify({ok:false, status:'failed', failureCode:'send_button_not_found', message:'未找到发送按钮'});
    }
    if (!clickElement(sendButton)) {
        return JSON.stringify({ok:false, status:'failed', failureCode:'send_button_click_failed', message:'发送按钮不可点击'});
    }
    await sleep(1200);

    const afterText = (document.body && document.body.innerText || '').toLowerCase();
    if (['验证码','滑块','拼图','captcha','verify','操作太频繁','稍后再试'].some(t => afterText.includes(t.toLowerCase()))) {
        return JSON.stringify({ok:false, status:'blocked', failureCode:'risk_control', message:'发送后检测到验证码或频率限制'});
    }
    return JSON.stringify({ok:true, status:'sent', failureCode:'', message:'已自动点击发送'});
})()"""

GREETING_SELECTOR_HEALTH_JS = r"""(function(){
    const bodyText = (document.body && document.body.innerText || '').toLowerCase();
    function visible(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    }
    function nearestActionable(el) {
        if (!el) return null;
        return el.closest('button,a,[role="button"],.btn,.btn-startchat,.start-chat,.op-btn,.btn-greet') || el;
    }
    function actionableByText(selectors, texts) {
        const candidates = Array.from(document.querySelectorAll(selectors))
            .filter(visible)
            .map(el => ({source: el, target: nearestActionable(el)}))
            .filter(item => item.target && visible(item.target))
            .filter(item => {
                const text = (item.target.innerText || item.target.textContent || item.source.innerText || item.source.textContent || '').trim();
                return texts.some(t => text.includes(t));
            });
        candidates.sort((a, b) => {
            const ar = a.target.getBoundingClientRect();
            const br = b.target.getBoundingClientRect();
            const aArea = ar.width * ar.height;
            const bArea = br.width * br.height;
            const aNative = /^(A|BUTTON)$/.test(a.target.tagName) ? 0 : 1;
            const bNative = /^(A|BUTTON)$/.test(b.target.tagName) ? 0 : 1;
            return aNative - bNative || aArea - bArea;
        });
        return candidates[0] ? candidates[0].target : null;
    }
    const chatButton = actionableByText('button,a,span,div', ['立即沟通','立即投递','投递简历','继续沟通']);
    const input = Array.from(document.querySelectorAll('#chat-input, textarea, [contenteditable="true"], [class*="chat-input"], [placeholder*="请输入"]')).find(visible);
    const sendButton = actionableByText('button,span,div,a', ['发送']);
    const risk = ['验证码','滑块','拼图','captcha','verify','操作太频繁','稍后再试','账号异常','限制使用'].some(t => bodyText.includes(t.toLowerCase()));
    const checks = [
        {key:'page_risk', status:risk ? 'error' : 'ok', message:risk ? '检测到验证码或风控提示' : '未检测到明显风控提示'},
        {key:'chat_button', status:chatButton ? 'ok' : 'error', message:chatButton ? '找到立即沟通按钮' : '未找到立即沟通按钮'},
        {key:'chat_input', status:input ? 'ok' : 'warn', message:input ? '当前页面已有输入框' : '详情页未直接显示输入框，点击沟通后再检测'},
        {key:'send_button', status:sendButton ? 'ok' : 'warn', message:sendButton ? '当前页面已有发送按钮' : '详情页未直接显示发送按钮，点击沟通后再检测'},
    ];
    return JSON.stringify({status: checks.some(c => c.status === 'error') ? 'error' : 'ok', checks});
})()"""


# ============================================================
#  CDPSession — CDP WebSocket 客户端
# ============================================================
class CDPSession:
    def __init__(self, port=CDP_PORT):
        resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=10)
        ws_url = resp.json()["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self._mid = 0

    def send(self, method, params=None, sid=None, timeout=30):
        """发送 CDP 命令并等待匹配 id 的响应。事件消息会被跳过。"""
        self._mid += 1
        msg = {"id": self._mid, "method": method, "params": params or {}}
        if sid:
            msg["sessionId"] = sid
        self.ws.send(json.dumps(msg))
        start = _time.time()
        while _time.time() - start < timeout:
            raw = self.ws.recv()
            try:
                r = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if r.get("id") == self._mid:
                return r
            event_name = r.get("method", "")
            if event_name:
                logger.debug("send(%s) 跳过: %s", method, event_name)
        raise TimeoutError(f"CDP {method} 超时")

    def eval_js(self, js, sid):
        """在页面中执行 JS 并返回结果。"""
        r = self.send("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True}, sid)
        result = r.get("result", {})
        if "exceptionDetails" in result:
            exc = result["exceptionDetails"]
            logger.warning("JS 异常: %s (line %d)", exc.get("text", "")[:200], exc.get("lineNumber", 0))
            return None
        return result.get("result", {}).get("value")

    def create_page(self):
        """创建空白页面（about:blank），返回 (targetId, sessionId)。
        
        关键：不显式调用 Page.enable / Runtime.enable。
        flatten attach 已隐式启用这些 domain，显式 enable 会订阅大量
        生命周期事件，send() 在跳过它们时会破坏页面状态。
        """
        r = self.send("Target.createTarget", {"url": "about:blank"})
        tid = r["result"]["targetId"]
        logger.info("创建目标页: %s", tid[:20])

        r = self.send("Target.attachToTarget", {"targetId": tid, "flatten": True})
        sid = r["result"]["sessionId"]
        logger.info("页面就绪: tid=%s sid=%s", tid[:20], sid[:20] if sid else "N/A")
        return tid, sid

    def navigate(self, url, sid):
        """导航到 URL 并等待 SPA 页面加载。
        
        对齐参考项目：Page.navigate + sleep(random 6-10s)。
        Boss 直聘是 SPA，简单 sleep 比事件等待更可靠。
        """
        r = self.send("Page.navigate", {"url": url}, sid)
        error = r.get("result", {}).get("errorText")
        if error:
            raise RuntimeError(f"Page.navigate 失败: {error}")
        logger.info("导航中: %s", url[:120])
        wait = random.uniform(6, 10)
        logger.debug("等待 %.1f 秒...", wait)
        _time.sleep(wait)
        current = self.eval_js("window.location.href", sid)
        logger.info("当前 URL: %s", str(current)[:120] if current else "N/A")

    def close(self):
        self.ws.close()


# ============================================================
#  Chrome 管理
# ============================================================
def _chrome_running():
    try:
        requests.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3)
        return True
    except Exception:
        return False


def _find_chrome() -> str:
    """跨平台查找 Chrome/Chromium 可执行文件。"""
    import shutil as _shutil
    bundled = os.environ.get("BOSS_WORKBENCH_BROWSER_EXECUTABLE", "").strip()
    if bundled and os.path.exists(bundled):
        return bundled
    candidates = []
    system = sys.platform
    if system == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "linux":
        candidates = [
            "google-chrome", "google-chrome-stable", "chromium",
            "chromium-browser", "/usr/bin/google-chrome",
        ]
    elif system == "win32":
        candidates = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]
    for c in candidates:
        if c and (_shutil.which(c) or os.path.exists(c)):
            return c
    raise RuntimeError(
        "未找到 Chrome/Chromium。请使用桌面端内置浏览器或安装 Google Chrome。\n"
        f"  系统: {system}\n"
        f"  搜索路径: {candidates[:3]}"
    )

def _launch_chrome(url="about:blank"):
    os.makedirs(CDP_PROFILE, exist_ok=True)
    _stop_chrome()
    _time.sleep(1)
    chrome = _find_chrome()
    chrome_log_path = workflow_persistence.DATA_DIR / "logs" / "chrome.log"
    chrome_log_path.parent.mkdir(parents=True, exist_ok=True)
    chrome_log = chrome_log_path.open("a", encoding="utf-8", buffering=1)
    chrome_log.write(f"\n=== Chrome launch port={CDP_PORT} executable={chrome} ===\n")
    try:
        subprocess.Popen(
            [
                chrome,
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={CDP_PROFILE}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-sync",
                "--window-size=1440,900",
                "--window-position=100,100",
                "--disable-blink-features=AutomationControlled",
                "--remote-allow-origins=*",
                "--enable-logging=stderr",
                "--log-file=" + str(chrome_log_path),
                url,
            ],
            stdout=chrome_log,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        chrome_log.close()
        logger.exception("Chrome 启动失败")
        raise
    finally:
        chrome_log.close()
    for _ in range(20):
        if _chrome_running():
            logger.info("Chrome CDP 已启动: port=%d", CDP_PORT)
            return True
        _time.sleep(0.5)
    logger.error("Chrome 启动后未监听 CDP 端口: %d", CDP_PORT)
    return False


def _stop_chrome(clear_session: bool = False):
    """仅停止我们启动的 CDP Chrome 进程（不影响用户正常 Chrome）。"""
    try:
        # macOS/Linux: 按端口精确匹配，避免误杀用户 Chrome
        import signal as _signal
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{CDP_PORT}"],
            capture_output=True, text=True, timeout=5,
        )
        for pid_str in result.stdout.strip().split("\n"):
            pid = pid_str.strip()
            if pid:
                try:
                    logger.info("关闭 Chrome CDP 进程: pid=%s port=%d", pid, CDP_PORT)
                    os.kill(int(pid), _signal.SIGTERM)
                except (OSError, ValueError):
                    pass
    except Exception:
        pass
    _time.sleep(0.5)
    if clear_session:
        session_file = Path(CDP_PROFILE) / ".boss_logged_in"
        if session_file.exists():
            session_file.unlink()


# ============================================================
#  登录探测
# ============================================================
def _probe_login(cdp, sid, query="Python", city_code="101010100"):
    """在 Boss 搜索 API 中探测是否已登录（检查 salaryDesc 字段）。"""
    params = urlencode({
        "scene": "1", "query": query, "city": city_code,
        "page": 1, "pageSize": 10,
    })
    api_url = f"{API_BASE}{API_SEARCH}?{params}"
    js = PROBE_JS.replace("__PROBE_URL__", api_url)
    raw = cdp.eval_js(js, sid)
    if raw is None:
        return {"status": "empty", "message": "探测响应为空（JS 异常）"}

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, ValueError):
        return {"status": "empty", "message": f"响应解析失败: {str(raw)[:100]}"}

    http_status = data.get("httpStatus", 0)
    if http_status != 200:
        return {"status": "error", "message": f"HTTP {http_status}"}

    body = data.get("body", "")
    if not body:
        return {"status": "empty", "message": "响应体为空"}

    try:
        body_data = json.loads(body) if isinstance(body, str) else body
    except (json.JSONDecodeError, ValueError):
        return {"status": "empty", "message": f"响应体解析失败: {str(body)[:100]}"}

    code = body_data.get("code")
    if code == 0:
        zp_data = body_data.get("zpData", {})
        jobs = zp_data.get("jobList", [])
        if jobs and "salaryDesc" in jobs[0]:
            sample = jobs[0].get("salaryDesc", "?")
            return {"status": "ok", "salary_sample": sample}
        return {"status": "empty", "message": "API code=0 但无 salaryDesc，可能未登录"}

    if code in (31, 37):
        return {"status": "restricted", "message": f"Boss 接口被限制 (code={code})"}

    msg = body_data.get("message", "")
    logger.info("探测: code=%s msg=%s", code, msg)
    return {"status": "empty", "message": f"未检测到登录态 (code={code})"}


# ============================================================
#  登录流程
# ============================================================
async def boss_login_and_save_session(headless=False):
    """打开 Chrome 让用户扫码登录 Boss 直聘。"""
    import asyncio

    logger.info("=== 登录 Boss 直聘 ===")

    if _chrome_running():
        _stop_chrome()
        _time.sleep(2)

    if not _launch_chrome():
        raise RuntimeError("Chrome 启动失败")

    _time.sleep(2)
    cdp = None
    tid = None

    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()
        cdp.navigate("https://www.zhipin.com/web/user/?intent=0&ka=header-geek", sid)

        logger.info("请在浏览器中扫码登录，等待中...")
        started = _time.time()
        timeout = 300

        while _time.time() - started < timeout:
            await asyncio.sleep(3)
            elapsed = int(_time.time() - started)
            if elapsed % 15 < 3:
                logger.info("  已等待 %d 秒...", elapsed)

            cdp.navigate("https://www.zhipin.com/web/geek/job?query=Python&city=101010100", sid)
            result = _probe_login(cdp, sid)
            if result["status"] == "ok":
                logger.info("登录成功！检测到明文薪资: %s", result.get("salary_sample"))
                # 保存登录成功标记
                session_file = Path(CDP_PROFILE) / ".boss_logged_in"
                session_file.write_text(datetime.now(timezone.utc).isoformat())
                return {"status": "ok", "message": f"登录成功（{result.get('salary_sample','')}）"}
            if result["status"] == "restricted":
                return {"status": "error", "message": "Boss 接口被限制，请稍后重试"}

        return {"status": "timeout", "message": "登录超时（5分钟）"}

    except Exception as e:
        logger.error("登录异常: %s", e)
        return {"status": "error", "message": str(e)}
    finally:
        if tid and cdp:
            try:
                cdp.send("Target.closeTarget", {"targetId": tid})
            except Exception:
                pass
        if cdp:
            try:
                cdp.close()
            except Exception:
                pass
        _stop_chrome()


# ============================================================
#  API: 抓取
# ============================================================
async def scrape_boss_jobs(keyword="Python", city="深圳", max_pages=3, headless=True, filters=None):
    """CDP + API 模式抓取 Boss 岗位。"""
    import asyncio

    logger.info("=== 抓取: %s @ %s (最多 %d 页) ===", keyword, city, max_pages)
    city_code = resolve_city_code(city)
    filters = filters or {}

    if not _chrome_running():
        if not _launch_chrome():
            raise RuntimeError("Chrome 启动失败，请先登录")

    cdp = None
    tid = None
    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()

        # 导航到搜索页
        base_params = {"query": keyword, "city": city_code}
        for key, value in filters.items():
            if value:
                base_params[key] = value
        search_url = f"https://www.zhipin.com/web/geek/job?{urlencode(base_params)}"
        cdp.navigate(search_url, sid)

        # 探测登录态
        probe = _probe_login(cdp, sid, query=keyword, city_code=city_code)
        if probe["status"] != "ok":
            raise RuntimeError(
                f"未登录或登录态失效 ({probe.get('message', probe['status'])}）。"
                f"请先点击「登录 Boss 直聘」扫码。"
            )
        logger.info("登录态有效: %s", probe.get("salary_sample", "?"))

        # 逐页抓取
        all_jobs = []
        seen = set()

        for pg in range(1, max_pages + 1):
            logger.info("第 %d/%d 页...", pg, max_pages)
            api_params = {
                "scene": "1", "query": keyword, "city": city_code,
                "page": pg, "pageSize": 30,
            }
            for key, value in filters.items():
                if value:
                    api_params[key] = value
            params = urlencode(api_params)
            api_url = f"{API_BASE}{API_SEARCH}?{params}"
            js = API_JS_TEMPLATE.replace("__API_URL__", api_url)

            raw = cdp.eval_js(js, sid)
            if raw is None:
                logger.warning("API 调用返回 None")
                break

            try:
                jobs = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, ValueError):
                logger.warning("API 返回解析失败: %s", str(raw)[:200])
                break

            if not jobs:
                logger.info("无更多数据")
                break

            for j in jobs:
                key = j.get("encrypt_job_id") or j.get("title", "")
                if key in seen:
                    continue
                seen.add(key)

                tags = [t for t in [j.get("exp"), j.get("degree"),
                                     j.get("scale"), j.get("stage")] if t and t != "不限"]
                jd_parts = list(filter(None, [j.get("labels"), j.get("skills"), j.get("welfare")]))

                all_jobs.append({
                    "title": j.get("title", ""),
                    "company": j.get("company", ""),
                    "city": city,
                    "salary": j.get("salary", ""),
                    "jd_text": " | ".join(jd_parts),
                    "keywords": tags,
                    "source_url": j.get("job_link", ""),
                    "source": "boss_api",
                    "boss_active": j.get("boss_active", ""),
                    "industry": j.get("industry", ""),
                })

            logger.info("  本页 %d 条，累计 %d", len(jobs), len(all_jobs))
            if len(jobs) < 30:
                break
            if pg < max_pages:
                await asyncio.sleep(random.uniform(6, 10))

        logger.info("抓取完成: %d 条", len(all_jobs))
        return all_jobs

    finally:
        if tid and cdp:
            try:
                cdp.send("Target.closeTarget", {"targetId": tid})
            except Exception:
                pass
        if cdp:
            try:
                cdp.close()
            except Exception:
                pass
        _stop_chrome()


def login_boss_sync(headless=False):
    import asyncio
    return asyncio.run(boss_login_and_save_session(headless=headless))


def scrape_jobs_sync(keyword="Python", city="深圳", max_pages=3, headless=True, filters=None):
    import asyncio
    return asyncio.run(scrape_boss_jobs(
        keyword=keyword, city=city, max_pages=max_pages, headless=headless, filters=filters
    ))


def send_boss_greeting_sync(job_url: str, message: str) -> dict:
    """打开岗位详情页，点击立即沟通，粘贴招呼语并点击发送。

    只做正常页面操作；遇到登录、验证码、风控、页面结构变化会停止并返回结构化原因。
    """
    if not job_url:
        return {"ok": False, "status": "failed", "failureCode": "missing_job_url", "message": "缺少岗位链接"}
    if not message.strip():
        return {"ok": False, "status": "failed", "failureCode": "empty_message", "message": "招呼语为空"}

    if not _chrome_running():
        if not _launch_chrome():
            return {"ok": False, "status": "blocked", "failureCode": "browser_start_failed", "message": "Chrome 启动失败"}

    cdp = None
    tid = None
    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()
        cdp.navigate(job_url, sid)
        probe = _probe_login(cdp, sid)
        if probe["status"] != "ok":
            reason = "risk_control" if probe.get("status") == "restricted" else "cookie_expired"
            return {"ok": False, "status": "blocked", "failureCode": reason, "message": probe.get("message") or "登录态无效"}
        js = GREETING_SEND_JS_TEMPLATE.replace("__MESSAGE_JSON__", json.dumps(message, ensure_ascii=False))
        raw = cdp.eval_js(js, sid)
        if raw is None:
            return {"ok": False, "status": "failed", "failureCode": "page_script_failed", "message": "页面脚本执行失败"}
        try:
            result = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {"ok": False, "status": "failed", "failureCode": "page_script_invalid", "message": str(raw)[:120]}
        return result if isinstance(result, dict) else {"ok": False, "status": "failed", "failureCode": "page_script_invalid", "message": "页面返回异常"}
    except Exception as e:
        return {"ok": False, "status": "failed", "failureCode": "browser_error", "message": str(e)}
    finally:
        if tid and cdp:
            try:
                cdp.send("Target.closeTarget", {"targetId": tid})
            except Exception:
                pass


def check_boss_greeting_selectors_sync(job_url: str) -> dict:
    """打开岗位详情页，只检测沟通相关选择器，不发送任何内容。"""
    if not job_url:
        return {"status": "error", "checks": [{"key": "job_url", "status": "error", "message": "缺少岗位链接"}]}
    if not _chrome_running():
        if not _launch_chrome():
            return {"status": "error", "checks": [{"key": "browser", "status": "error", "message": "Chrome 启动失败"}]}
    cdp = None
    tid = None
    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()
        cdp.navigate(job_url, sid)
        probe = _probe_login(cdp, sid)
        if probe["status"] != "ok":
            return {
                "status": "error",
                "checks": [{"key": "boss_login", "status": "error", "message": probe.get("message") or "登录态无效"}],
            }
        raw = cdp.eval_js(GREETING_SELECTOR_HEALTH_JS, sid)
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {"status": "error", "checks": [{"key": "page_script", "status": "error", "message": "选择器检测返回异常"}]}
    except Exception as e:
        return {"status": "error", "checks": [{"key": "browser_error", "status": "error", "message": str(e)}]}
    finally:
        if tid and cdp:
            try:
                cdp.send("Target.closeTarget", {"targetId": tid})
            except Exception:
                pass
        if cdp:
            try:
                cdp.close()
            except Exception:
                pass
        _stop_chrome()


# ============================================================
#  详情页 JD 提取
# ============================================================
# EXTRACT_DETAIL_JS 从独立文件加载，避免 Python/JS 转义冲突
with open(Path(__file__).parent / "extract_detail.js", "r") as _f:
    EXTRACT_DETAIL_JS = _f.read()


def scrape_job_detail(cdp, sid, job_url):
    """导航到岗位详情页并提取 JD。

    返回 {"jd": str, "jd_tags": list, "url": str}
    """
    logger.info("抓取详情: %s", job_url[:100])
    cdp.navigate(job_url, sid)

    # 模拟人类滚动
    for _ in range(random.randint(2, 4)):
        delta = random.randint(200, 500)
        cdp.eval_js(f"window.scrollBy(0,{delta})", sid)
        _time.sleep(random.uniform(0.8, 2.0))

    raw = cdp.eval_js(EXTRACT_DETAIL_JS, sid)
    try:
        return json.loads(raw) if isinstance(raw, str) else {"jd": "", "jd_tags": []}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"jd": "", "jd_tags": []}


def _is_recoverable_cdp_error(error: Exception) -> bool:
    return isinstance(error, (ConnectionError, TimeoutError, OSError, websocket.WebSocketException))


def _close_detail_session(cdp, tid) -> None:
    if tid and cdp:
        try:
            cdp.send("Target.closeTarget", {"targetId": tid})
        except Exception:
            pass
    if cdp:
        try:
            cdp.close()
        except Exception:
            pass


def _emit_detail_progress(on_progress, job, done, total, success, reason="") -> None:
    if not on_progress:
        return
    try:
        on_progress(job, done, total, success, reason)
    except Exception as error:
        logger.warning("JD 进度保存失败，不中断后续抓取: %s", error)


def enrich_jobs_with_details(jobs, max_jobs=30, on_progress=None, preserve_browser_on_all_failures=False):
    """为岗位列表补充详情页 JD（同步版本）。"""
    global _detail_enrich_running

    logger.info("JD 任务开始: requested=%d max_jobs=%d", len(jobs or []), max_jobs)
    if not _chrome_running():
        if not _launch_chrome():
            raise RuntimeError("Chrome 启动失败")

    cdp = None
    tid = None
    preserve_browser = False
    try:
        _detail_enrich_running = True
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()

        # 筛选需要补充的岗位（兼容 dict 和 Pydantic model）
        to_process = []
        for j in jobs:
            url = j.source_url if hasattr(j, 'source_url') else j.get("source_url", "")
            if url:
                to_process.append(j)
        to_process = to_process[:max_jobs]

        logger.info("开始补充 %d 个岗位的详情 JD...", len(to_process))
        enriched = 0
        recovery_used = False

        for i, job in enumerate(to_process):
            title = job.title if hasattr(job, 'title') else job.get("title", "")
            source_url = job.source_url if hasattr(job, 'source_url') else job.get("source_url", "")
            keywords = job.keywords if hasattr(job, 'keywords') else job.get("keywords", [])

            logger.info("[%d/%d] %s", i + 1, len(to_process), title[:30])
            detail = None
            failure_reason = ""
            try:
                detail = scrape_job_detail(cdp, sid, source_url)
            except Exception as e:
                failure_reason = str(e)
                should_recover = not recovery_used and (_is_recoverable_cdp_error(e) or not _chrome_running())
                if should_recover:
                    recovery_used = True
                    logger.warning("  CDP 会话中断，重建浏览器后重试当前 JD: %s", e)
                    _close_detail_session(cdp, tid)
                    cdp = None
                    tid = None
                    _stop_chrome()
                    try:
                        if not _launch_chrome():
                            raise RuntimeError("Chrome 重建失败")
                        cdp = CDPSession(CDP_PORT)
                        tid, sid = cdp.create_page()
                        detail = scrape_job_detail(cdp, sid, source_url)
                        failure_reason = ""
                    except Exception as retry_error:
                        failure_reason = str(retry_error)
                        logger.warning("  CDP 会话重建后仍无法抓取: %s", retry_error)
                else:
                    logger.warning("  详情抓取异常: %s", e)

            if detail and detail.get("jd") and len(detail["jd"]) > 50:
                if hasattr(job, 'jd_text'):
                    job.jd_text = detail["jd"]
                    job.jd_detail_fetched_at = datetime.now(timezone.utc).isoformat()
                    job.jd_detail_url = source_url
                else:
                    job["jd_text"] = detail["jd"]
                    job["jd_detail_fetched_at"] = datetime.now(timezone.utc).isoformat()
                    job["jd_detail_url"] = source_url

                # 同步获取企业工商注册名称
                company_name = detail.get("company_name", "")
                if company_name and len(company_name) >= 3:
                    if hasattr(job, 'tags'):
                        if not job.capture_company_name:
                            job.capture_company_name = job.company
                        job.company = company_name
                        job.tags = [t for t in (job.tags or []) if not t.startswith("@")]
                    elif isinstance(job, dict):
                        if not job.get("capture_company_name"):
                            job["capture_company_name"] = job.get("company", "")
                        job["company"] = company_name
                        job["tags"] = [t for t in job.get("tags", []) if not t.startswith("@")]

                if detail.get("jd_tags"):
                    existing = set(keywords or [])
                    new_tags = [t for t in detail["jd_tags"] if t not in existing and len(t) < 20]
                    if hasattr(job, 'keywords'):
                        job.keywords = list(keywords or []) + new_tags
                    else:
                        job["keywords"] = list(keywords or []) + new_tags

                enriched += 1
                logger.info("  JD: %d 字符", len(detail["jd"]))
                logger.info("JD 进度: %d/%d success", i + 1, len(to_process))
                _emit_detail_progress(on_progress, job, i + 1, len(to_process), True)
            else:
                reason = failure_reason or "未提取到有效 JD"
                logger.info("  %s", reason)
                logger.warning("JD 进度: %d/%d failed reason=%s", i + 1, len(to_process), reason[:200])
                _emit_detail_progress(on_progress, job, i + 1, len(to_process), False, reason)

            if i < len(to_process) - 1:
                _time.sleep(random.uniform(2, 4))

        logger.info("详情补充完成: %d/%d", enriched, len(to_process))
        preserve_browser = preserve_browser_on_all_failures and bool(to_process) and enriched == 0
        return enriched

    finally:
        if preserve_browser:
            if cdp:
                try:
                    cdp.close()
                except Exception:
                    pass
            logger.warning("JD 全部抓取失败，保留 BOSS 浏览器供人工检查")
        else:
            _close_detail_session(cdp, tid)
            _stop_chrome()
            logger.info("JD 任务结束，已关闭 Chrome: success=%d total=%d", enriched, len(to_process))
        _detail_enrich_running = False


def check_login_status(*, probe: bool = True) -> dict:
    """检查 BOSS 直聘是否已登录。
    
    probe=True（默认）时，会通过应用自己的 CDP Chrome 实际导航验证 Cookie 有效性；
    probe=False 时仅检查本地登录标记文件，不触发浏览器页面。
    显式探测无法完成时不会信任过期的本地登录标记。
    """
    session_file = Path(CDP_PROFILE) / ".boss_logged_in"
    if _detail_enrich_running:
        return _session_file_status(session_file) if session_file.exists() else _not_logged_in_status()

    if not probe:
        return _session_file_status(session_file) if session_file.exists() else _not_logged_in_status()

    started_here = False
    if not _chrome_running():
        try:
            started_here = bool(_launch_chrome())
        except Exception as e:
            logger.warning("启动 Chrome 进行登录探测失败: %s", e)
        if not started_here:
            if session_file.exists():
                session_file.unlink(missing_ok=True)
            return {
                **_not_logged_in_status(),
                "reason": "probe_unavailable",
                "message": "无法启动浏览器完成登录检测",
                "action": "请重新启动桌面端后再检测",
            }

    cdp = None
    tid = None
    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()
        cdp.navigate("https://www.zhipin.com", sid)
        result = _probe_login(cdp, sid)
        if result["status"] == "ok":
            session_file.parent.mkdir(parents=True, exist_ok=True)
            if not session_file.exists():
                session_file.write_text(datetime.now(timezone.utc).isoformat())
            return {"logged_in": True, "reason": "ok", "message": "已登录", "action": ""}

        session_file.unlink(missing_ok=True)
        logger.info("登录态探测未通过，清除本地登录标记")
        reason = "restricted" if result.get("status") == "restricted" else "cookie_expired"
        action = "疑似页面风控，请稍后重试" if reason == "restricted" else "请重新扫码登录 BOSS 直聘"
        return {"logged_in": False, "reason": reason, "message": result.get("message") or "未登录", "action": action}
    except Exception as e:
        logger.warning("登录态探测失败: %s", e)
        session_file.unlink(missing_ok=True)
        return {
            **_not_logged_in_status(),
            "reason": "probe_failed",
            "message": "登录状态检测失败，未能确认当前账号",
            "action": "请确认网络正常后再次检测",
        }
    finally:
        if tid and cdp:
            try:
                cdp.send("Target.closeTarget", {"targetId": tid})
            except Exception:
                pass
        if cdp:
            try:
                cdp.close()
            except Exception:
                pass
        if started_here:
            _stop_chrome()


def _not_logged_in_status() -> dict:
    return {
        "logged_in": False,
        "reason": "not_logged_in",
        "message": "未登录",
        "action": "请点击「登录 Boss 直聘」并扫码登录",
    }


def _session_file_status(session_file: Path) -> dict:
    try:
        login_time = session_file.read_text().strip()
        return {"logged_in": True, "reason": "session_file", "message": f"已登录 (登录时间: {login_time[:10]})", "action": "Chrome 未运行时使用本地登录标记判断"}
    except Exception:
        return {"logged_in": False, "reason": "session_file_missing", "message": "未登录", "action": "请重新登录"}
