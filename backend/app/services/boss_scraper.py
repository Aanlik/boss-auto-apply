"""
Boss 直聘岗位抓取服务 — CDP + API 模式
基于 eatmoreduck/boss-zhipin-scraper 的 CDP 架构：
  - 连接系统 Chrome 的 CDP 调试端口
  - 在页面中执行 JS 调 Boss 内部搜索 API
  - API 返回明文薪资数据，绕过字体反爬

关键设计（对齐 eatmoreduck/boss-zhipin-scraper）：
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

logger = logging.getLogger("boss_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOSS] %(message)s", datefmt="%H:%M:%S")

# ——— 配置 ———
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CDP_PROFILE = str(DATA_DIR / "chrome_profile")
CDP_PORT = 9222
API_SEARCH = "/wapi/zpgeek/search/joblist.json"
API_BASE = "https://www.zhipin.com"

CITY_CODES = {
    "深圳": "101280600", "北京": "101010100", "上海": "101020100",
    "广州": "101280100", "杭州": "101210100", "成都": "101270100",
    "南京": "101190100", "武汉": "101200100", "西安": "101110100", "苏州": "101190400",
    "郑州": "101180100", "长沙": "101250100", "重庆": "101040100",
    "天津": "101030100", "合肥": "101220100", "济南": "101120100",
    "青岛": "101120200", "厦门": "101230200", "福州": "101230100",
    "东莞": "101281600", "佛山": "101280800", "珠海": "101280700",
    "大连": "101070200", "昆明": "101290100", "贵阳": "101260100",
    "南宁": "101300100", "南昌": "101240100", "石家庄": "101090100",
    "太原": "101100100", "沈阳": "101070100", "哈尔滨": "101050100",
    "长春": "101060100", "兰州": "101160100", "海口": "101310100",
    "无锡": "101190200", "宁波": "101210400", "温州": "101210700",
}

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
        r = self.send("Runtime.evaluate", {"expression": js, "returnByValue": True}, sid)
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


def _launch_chrome(url="about:blank"):
    os.makedirs(CDP_PROFILE, exist_ok=True)
    _stop_chrome()
    _time.sleep(1)
    subprocess.Popen(
        [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={CDP_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--remote-allow-origins=*",
            url,
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if _chrome_running():
            logger.info("Chrome CDP 已启动: port=%d", CDP_PORT)
            return True
        _time.sleep(0.5)
    return False


def _stop_chrome():
    try:
        subprocess.run(
            ["pkill", "-f", f"remote-debugging-port={CDP_PORT}"],
            timeout=5,
        )
    except Exception:
        pass


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
    cdp = CDPSession(CDP_PORT)

    try:
        tid, sid = cdp.create_page()
        cdp.navigate("https://www.zhipin.com/web/user/?ka=header-login", sid)

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
                cdp.send("Target.closeTarget", {"targetId": tid})
                cdp.close()
                return {"status": "ok", "message": f"登录成功（{result.get('salary_sample','')}）"}
            if result["status"] == "restricted":
                cdp.close()
                _stop_chrome()
                return {"status": "error", "message": "Boss 接口被限制，请稍后重试"}

        cdp.send("Target.closeTarget", {"targetId": tid})
        cdp.close()
        return {"status": "timeout", "message": "登录超时（5分钟）"}

    except Exception as e:
        logger.error("登录异常: %s", e)
        try:
            cdp.close()
        except Exception:
            pass
        return {"status": "error", "message": str(e)}


# ============================================================
#  API: 抓取
# ============================================================
async def scrape_boss_jobs(keyword="Python", city="深圳", max_pages=3, headless=True):
    """CDP + API 模式抓取 Boss 岗位。"""
    import asyncio

    logger.info("=== 抓取: %s @ %s (最多 %d 页) ===", keyword, city, max_pages)
    city_code = CITY_CODES.get(city, "101280600")

    if not _chrome_running():
        if not _launch_chrome():
            raise RuntimeError("Chrome 启动失败，请先登录")

    cdp = None
    tid = None
    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()

        # 导航到搜索页
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
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
            params = urlencode({
                "scene": "1", "query": keyword, "city": city_code,
                "page": pg, "pageSize": 30,
            })
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


def login_boss_sync(headless=False):
    import asyncio
    return asyncio.run(boss_login_and_save_session(headless=headless))


def scrape_jobs_sync(keyword="Python", city="深圳", max_pages=3, headless=True):
    import asyncio
    return asyncio.run(scrape_boss_jobs(
        keyword=keyword, city=city, max_pages=max_pages, headless=headless
    ))


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


def enrich_jobs_with_details(jobs, max_jobs=30):
    """为岗位列表补充详情页 JD（同步版本）。"""

    if not _chrome_running():
        if not _launch_chrome():
            raise RuntimeError("Chrome 启动失败")

    cdp = None
    tid = None
    try:
        cdp = CDPSession(CDP_PORT)
        tid, sid = cdp.create_page()

        # 先导航到 Boss 保证 cookie 生效
        cdp.navigate("https://www.zhipin.com", sid)

        # 筛选需要补充的岗位（兼容 dict 和 Pydantic model）
        to_process = []
        for j in jobs:
            url = j.source_url if hasattr(j, 'source_url') else j.get("source_url", "")
            if url:
                to_process.append(j)
        to_process = to_process[:max_jobs]

        logger.info("开始补充 %d 个岗位的详情 JD...", len(to_process))
        enriched = 0

        for i, job in enumerate(to_process):
            title = job.title if hasattr(job, 'title') else job.get("title", "")
            source_url = job.source_url if hasattr(job, 'source_url') else job.get("source_url", "")
            keywords = job.keywords if hasattr(job, 'keywords') else job.get("keywords", [])

            logger.info("[%d/%d] %s", i + 1, len(to_process), title[:30])
            try:
                detail = scrape_job_detail(cdp, sid, source_url)
                if detail.get("jd") and len(detail["jd"]) > 50:
                    if hasattr(job, 'jd_text'):
                        job.jd_text = detail["jd"]
                    else:
                        job["jd_text"] = detail["jd"]

                    if detail.get("jd_tags"):
                        existing = set(keywords or [])
                        new_tags = [t for t in detail["jd_tags"] if t not in existing and len(t) < 20]
                        if hasattr(job, 'keywords'):
                            job.keywords = list(keywords or []) + new_tags
                        else:
                            job["keywords"] = list(keywords or []) + new_tags

                    enriched += 1
                    logger.info("  JD: %d 字符", len(detail["jd"]))
                else:
                    logger.info("  未提取到 JD")
            except Exception as e:
                logger.warning("  详情抓取异常: %s", e)

            if i < len(to_process) - 1:
                _time.sleep(random.uniform(2, 4))

        logger.info("详情补充完成: %d/%d", enriched, len(to_process))
        return jobs

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
