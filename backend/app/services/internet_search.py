"""
AI 驱动的互联网搜索 — 百度千帆智能搜索 API

端点: POST https://qianfan.baidubce.com/v2/ai_search/chat/completions
鉴权: Authorization: Bearer <API_KEY>
免费: 100次/天

工作流:
  1. 发送优化后的搜索提示词到千帆 → 获取 AI 总结 + 引用
  2. 将千帆总结喂给用户配置的 AI → 结构化提取 + 打分
"""

import json
import logging
import time
import os
import re
from pathlib import Path

import aiohttp

from app.services.ai_client import get_ai_client
from app.services.external_service import ProviderFailure, async_run_with_resilience, test_mode_enabled
from app.services.secret_store import decrypt_secret

logger = logging.getLogger(__name__)

QIANFAN_API_KEY = ""
QIANFAN_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"
_search_cache: dict[str, dict] = {}


def load_baidu_config():
    global QIANFAN_API_KEY
    try:
        cfg_file = Path(__file__).resolve().parents[3] / "data" / "baidu_config.json"
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text())
            key = decrypt_secret(str(cfg.get("api_key_encrypted") or "")) if cfg.get("api_key_encrypted") else cfg.get("api_key", "")
            key = key or os.environ.get("BAIDU_API_KEY", "")
            if key:
                QIANFAN_API_KEY = key
                logger.info("千帆智能搜索 API Key 已加载")
    except Exception:
        pass


load_baidu_config()


# ═══════════════════════════════════════════════════════════
#  提示词模板（针对不同搜索类型优化）
# ═══════════════════════════════════════════════════════════

def _build_search_prompt(search_type: str, company_name: str, extra: str = "") -> str:
    """构建优化的千帆搜索提示词"""
    templates = {
        "company_info": (
            f"请全面搜索并总结「{company_name}」公司的以下信息：\n"
            f"1. 公司规模和员工数量\n"
            f"2. 融资历史和最新融资阶段\n"
            f"3. 成立时间和发展历程\n"
            f"4. 主营业务、核心产品和商业模式\n"
            f"5. 核心技术栈和研发能力\n"
            f"6. 行业地位和竞争优势\n"
            f"7. 主要竞争对手\n"
            f"请用中文回答，每条信息注明来源。如果某项无法确定，请明确说明。"
        ),
        "sentiment": (
            f"请全面搜索并总结「{company_name}」公司的以下舆情信息：\n"
            f"1. 员工评价和口碑（如工作环境、薪资待遇、管理风格）\n"
            f"2. 近期是否有裁员、欠薪、劳动纠纷等负面事件\n"
            f"3. 工商处罚、法律诉讼等经营风险\n"
            f"4. 正面评价（如发展前景、技术实力、行业口碑）\n"
            f"5. 在招聘平台（脉脉、看准网等）上的整体评分\n"
            f"请用中文回答，正面和负面信息都要如实列出，注明信息来源。"
        ),
        "industry": (
            f"请全面分析「{company_name}」公司所在行业的发展前景：\n"
            f"公司业务：{extra}\n"
            f"请从以下维度分析：\n"
            f"1. 所属行业及细分领域\n"
            f"2. 当前行业趋势（上升期/稳定期/下行期），附具体数据\n"
            f"3. 国家政策环境（支持/中性/收紧），附相关政策名称\n"
            f"4. 市场规模和增长空间（如千亿级/百亿级）\n"
            f"5. 行业增速和预测\n"
            f"6. 主要风险和不确定性\n"
            f"请用中文回答，每条观点提供数据或来源支撑。"
        ),
    }
    return templates.get(search_type, f"请搜索并总结关于「{company_name}」的信息。")


# ═══════════════════════════════════════════════════════════
#  千帆搜索核心调用
# ═══════════════════════════════════════════════════════════

async def _qianfan_search(prompt: str, max_results: int = 8) -> dict:
    """调用千帆智能搜索，返回 AI 总结 + 引用来源"""
    if test_mode_enabled():
        return {"summary": "", "references": [], "error": "", "testMode": True}
    if not QIANFAN_API_KEY:
        return {}
    try:
        return await async_run_with_resilience(
            "baidu",
            lambda: _qianfan_search_once(prompt, max_results),
            max_attempts=3,
            base_delay=0.25,
            circuit_threshold=3,
        )
    except ProviderFailure as exc:
        return {
            "summary": "",
            "references": [],
            "error": str(exc),
            "errorMeta": exc.public_payload(),
        }


async def _qianfan_search_once(prompt: str, max_results: int = 8) -> dict:
    try:
        headers = {
            "Authorization": f"Bearer {QIANFAN_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "enable_corner_markers": True,
            "enable_followup_queries": False,
            "max_refer_search_items": max_results,
            "max_completion_tokens": "3000",
        }

        started = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                QIANFAN_SEARCH_URL, json=payload,
                headers=headers, timeout=30
            ) as resp:
                try:
                    from app.services.maintenance_service import log_api_call
                    log_api_call("baidu_search", "POST", QIANFAN_SEARCH_URL, resp.status, int((time.time() - started) * 1000), {"max_results": max_results})
                except Exception:
                    pass
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning("千帆搜索 %d: %s", resp.status, text[:300])
                    if resp.status == 429 or resp.status >= 500:
                        raise ProviderFailure(
                            "baidu",
                            "rate_limit" if resp.status == 429 else "provider",
                            f"HTTP {resp.status}: {text[:200]}",
                            status_code=resp.status,
                        )
                    return {"error": f"HTTP {resp.status}: {text[:200]}"}
                data = await resp.json()

        result = _parse_qianfan_response(data)
        logger.info("千帆搜索 → %d 字总结, %d 条引用",
                     len(result.get("summary", "")),
                     len(result.get("references", [])))
        return result

    except ProviderFailure:
        raise
    except Exception as e:
        logger.warning("千帆搜索异常: %s", e)
        return {"error": str(e)}


def _parse_qianfan_response(data: dict) -> dict:
    """解析千帆响应"""
    result = {"summary": "", "references": [], "error": ""}
    try:
        choices = data.get("choices", [])
        if choices:
            result["summary"] = choices[0].get("message", {}).get("content", "")

        search_results = data.get("web_search_results", []) or data.get("references", [])
        for ref in search_results:
            url = ref.get("url", "") or ref.get("link", "")
            result["references"].append({
                "title": ref.get("title", ""),
                "url": url,
                "snippet": ref.get("snippet", "") or ref.get("description", ""),
            })
    except Exception as e:
        result["error"] = str(e)
    return result


async def test_qianfan_connection() -> dict:
    """测试千帆 API 连接是否正常"""
    if not QIANFAN_API_KEY:
        return {"ok": False, "message": "未配置千帆 API Key"}

    try:
        headers = {
            "Authorization": f"Bearer {QIANFAN_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己"}],
            "max_completion_tokens": "50",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                QIANFAN_SEARCH_URL, json=payload,
                headers=headers, timeout=20
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return {"ok": True, "message": f"连接成功 — {content[:80]}"}
                else:
                    text = await resp.text()
                    return {"ok": False, "message": f"HTTP {resp.status}: {text[:150]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)[:200]}


# ═══════════════════════════════════════════════════════════
#  AI 提取（千帆结果 → 用户配置的 AI → 结构化 JSON）
# ═══════════════════════════════════════════════════════════

def _build_extraction_prompt(instruction: str, summary: str, schema: dict) -> str:
    return f"""{instruction}

以下是千帆智能搜索的搜索结果总结：

{summary}

请根据以上信息，以 JSON 格式返回：
{json.dumps(schema, ensure_ascii=False, indent=2)}

要求：只返回 JSON，不要任何解释。无法确定的信息写"未知"或空数组。"""


def _parse_json_response(response: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


async def _extract_with_ai(client, instruction: str, summary: str, schema: dict) -> dict:
    """用用户配置的 AI 从千帆总结中提取结构化数据"""
    prompt = _build_extraction_prompt(instruction, summary, schema)
    try:
        response = await client.chat(prompt, temperature=0.2, max_tokens=1000)
        return _parse_json_response(response)
    except Exception as e:
        logger.warning(f"AI 提取失败: {e}")
        return {}


# ═══════════════════════════════════════════════════════════
#  公开搜索接口
# ═══════════════════════════════════════════════════════════

async def search_company_info(company_name: str) -> dict:
    cache_key = f"info:{company_name}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    client = get_ai_client()
    prompt = _build_search_prompt("company_info", company_name)
    result = await _qianfan_search(prompt)

    summary = result.get("summary", "")
    if result.get("error"):
        logger.warning("千帆公司搜索失败: %s", result["error"])

    if client and summary:
        info = await _extract_with_ai(client,
            f"提取公司「{company_name}」的结构化信息。",
            summary, {
                "scale": "公司规模", "funding": "融资阶段", "founded": "成立年份",
                "business": "主营业务（2-3句话）", "tech_stack": ["核心技术"],
                "industry_position": "行业地位", "competitors": ["竞争对手"],
            }
        )
        _search_cache[cache_key] = info
        return info

    if client and not summary:
        info = await _extract_with_ai(client,
            f"基于你的知识，提取公司「{company_name}」的信息。不确定写未知。",
            "", {"scale": "", "funding": "", "business": "", "tech_stack": [],
                 "industry_position": "", "competitors": []}
        )
        if info:
            _search_cache[cache_key] = info
            return info

    return _fallback_company_info(company_name)


async def search_company_sentiment(company_name: str) -> dict:
    cache_key = f"sentiment:{company_name}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    client = get_ai_client()
    prompt = _build_search_prompt("sentiment", company_name)
    result = await _qianfan_search(prompt)

    summary = result.get("summary", "")
    if client and summary:
        info = await _extract_with_ai(client,
            f"提取公司「{company_name}」的舆情信息，如实列出正面和负面。",
            summary, {
                "positive_signals": ["正面信息"], "negative_signals": ["负面信息"],
                "employee_feedback": "员工整体评价（1-2句话）",
                "legal_risks": ["法律/经营风险"],
            }
        )
        _search_cache[cache_key] = info
        return info

    if client and not summary:
        info = await _extract_with_ai(client,
            f"基于你的知识，分析公司「{company_name}」的舆情。",
            "", {"positive_signals": [], "negative_signals": [],
                 "employee_feedback": "", "legal_risks": []}
        )
        if info:
            _search_cache[cache_key] = info
            return info

    return _fallback_sentiment()


async def search_industry_outlook(company_name: str, business: str = "") -> dict:
    cache_key = f"industry:{company_name}:{business}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    client = get_ai_client()
    prompt = _build_search_prompt("industry", company_name, business)
    result = await _qianfan_search(prompt)

    summary = result.get("summary", "")
    if client and summary:
        info = await _extract_with_ai(client,
            f"分析公司「{company_name}」所在行业的发展前景。",
            summary, {
                "industry": "所属行业", "trend": "行业趋势",
                "policy": "政策环境", "market_space": "市场空间",
                "growth_rate": "行业增速",
                "advantages": ["行业优势和机会"],
                "disadvantages": ["行业劣势和挑战"],
                "risks": ["行业风险"],
            }
        )
        _search_cache[cache_key] = info
        return info

    if client and not summary:
        info = await _extract_with_ai(client,
            f"分析公司「{company_name}」的行业前景（业务：{business}）。",
            "", {"industry": "", "trend": "", "policy": "",
                 "market_space": "", "growth_rate": "",
                 "advantages": [], "disadvantages": [], "risks": []}
        )
        if info:
            _search_cache[cache_key] = info
            return info

    return _fallback_industry()


# ── Fallback ──

def _fallback_company_info(name: str) -> dict:
    return {"scale": "未知", "funding": "未知", "founded": "未知",
            "business": f"关于{name}的详细信息暂未获取。",
            "tech_stack": [], "industry_position": "未知", "competitors": []}

def _fallback_sentiment() -> dict:
    return {"positive_signals": [], "negative_signals": [],
            "employee_feedback": "暂无数据", "legal_risks": []}

def _fallback_industry() -> dict:
    return {"industry": "未知", "trend": "待分析", "policy": "待分析",
            "market_space": "待分析", "growth_rate": "待分析",
            "advantages": [], "disadvantages": [], "risks": []}
