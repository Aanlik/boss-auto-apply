"""
企业工商信息服务 — 腾讯云市场企业工商全量查询

接入方式: 腾讯云市场 → SecretId/SecretKey 鉴权
输入: 公司全称 / 注册号 / 统一社会信用代码
输出: 工商基本信息、法人、注册资本、股东、高管、经营异常等数十项字段

调用格式:
  POST https://ap-shanghai.cloudmarket-apigw.com/service-6dr7ul9n/enterprise/business/all
  Content-Type: application/json
  Authorization: {"id":"<SecretId>", "x-date":"<GMT 时间>", "signature":"<签名>"}
  Query: keyword=公司名称
"""
from __future__ import annotations

import base64
from email.utils import formatdate
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import uuid
from typing import Optional

import aiohttp
from app.services.workflow_persistence import write_json_atomic

logger = logging.getLogger(__name__)

# ── 配置 ──
CONFIG_FILE = Path(__file__).resolve().parents[3] / "data" / "business_info_config.json"

# 默认端点（腾讯云市场 CloudMarket API Gateway）
DEFAULT_ENDPOINT = "https://ap-shanghai.cloudmarket-apigw.com/service-6dr7ul9n/enterprise/business/all"
LEGACY_ENDPOINTS = {
    "https://api.jumeiapi.com/business/info",
    "http://api.jumeiapi.com/business/info",
    "https://ap-guangzhou.market.tencentcloudapi.com/business/info",
    "http://ap-guangzhou.market.tencentcloudapi.com/business/info",
}

_secret_id: str = ""
_secret_key: str = ""
_endpoint: str = DEFAULT_ENDPOINT


def _normalize_endpoint(endpoint: str = "") -> str:
    """归一化文档里可能写成 http&https://... 的端点。"""
    value = (endpoint or "").strip()
    if not value:
        return DEFAULT_ENDPOINT
    if value.startswith("http&https://"):
        return "https://" + value[len("http&https://"):]
    if value.startswith("http&http://"):
        return "http://" + value[len("http&http://"):]
    if value.startswith("http&"):
        value = value[len("http&"):]
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    value = value.rstrip("/")
    if value in LEGACY_ENDPOINTS or value.endswith(".market.tencentcloudapi.com/business/info"):
        return DEFAULT_ENDPOINT
    return value


def _load_config():
    """从配置文件加载密钥。"""
    global _secret_id, _secret_key, _endpoint
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text())
            _secret_id = cfg.get("secret_id", "") or os.environ.get("TENCENT_SECRET_ID", "")
            _secret_key = cfg.get("secret_key", "") or os.environ.get("TENCENT_SECRET_KEY", "")
            raw_endpoint = cfg.get("endpoint", "")
            _endpoint = _normalize_endpoint(raw_endpoint)
            if raw_endpoint and raw_endpoint != _endpoint:
                cfg["endpoint"] = _endpoint
                write_json_atomic(CONFIG_FILE, cfg)
            if _secret_id:
                logger.info("工商 API 配置已加载")
    except Exception as e:
        logger.warning("加载工商 API 配置失败: %s", e)


def get_config() -> dict:
    return {
        "secret_id": _secret_id,
        "secret_key": _secret_key,
        "endpoint": _endpoint,
        "configured": bool(_secret_id and _secret_key),
    }


def set_config(secret_id: str, secret_key: str, endpoint: str = "") -> bool:
    """保存配置到文件。"""
    global _secret_id, _secret_key, _endpoint
    _secret_id = secret_id
    _secret_key = secret_key
    _endpoint = _normalize_endpoint(endpoint)
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(CONFIG_FILE, {
            "secret_id": _secret_id,
            "secret_key": _secret_key,
            "endpoint": _endpoint,
        })
        return True
    except Exception as e:
        logger.error("保存工商 API 配置失败: %s", e)
        return False


def clear_config():
    """清除配置。"""
    global _secret_id, _secret_key, _endpoint
    _secret_id = _secret_key = ""
    _endpoint = DEFAULT_ENDPOINT
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(CONFIG_FILE, {"secret_id": "", "secret_key": "", "endpoint": DEFAULT_ENDPOINT})
    except OSError as e:
        logger.warning("清除工商 API 配置失败: %s", e)


# ═══════════════════════════════════════════════════════════
#  API 调用
# ═══════════════════════════════════════════════════════════

# 缓存：避免同一公司重复调用
_info_cache: dict[str, dict] = {}


async def query_business_info(company_name: str) -> dict:
    """
    查询企业工商信息。

    参数:
      company_name: 公司全称（如「深圳市腾讯计算机系统有限公司」）

    返回: {
      "companyName": str,
      "legalRepresentative": str,     # 法人
      "registrationCapital": str,     # 注册资本
      "paidInCapital": str,           # 实缴资本
      "establishedDate": str,         # 成立日期
      "businessStatus": str,          # 经营状态
      "unifiedCreditCode": str,       # 统一信用代码
      "registrationNumber": str,      # 注册号
      "taxpayerId": str,              # 纳税人识别号
      "businessScope": str,           # 经营范围
      "industry": str,                # 所属行业
      "address": str,                 # 注册地址
      "shareholders": list[str],      # 股东列表
      "executives": list[str],        # 高管列表
      "branchCount": int,             # 分支机构数
      "abnormalInfo": list[str],      # 经营异常
      "penalties": list[str],         # 行政处罚
      "annualReport": str,            # 年报状态
      "raw": dict,                    # 原始返回数据
    }
    """
    if not company_name or not company_name.strip():
        return {"companyName": "", "error": "公司名称不能为空"}

    company_name = company_name.strip()

    # 检查缓存
    if company_name in _info_cache:
        logger.info("工商信息命中缓存: %s", company_name)
        return _info_cache[company_name]

    if not _secret_id or not _secret_key:
        return {
            "companyName": company_name,
            "error": "未配置腾讯云工商 API，请在设置中配置 SecretId 和 SecretKey",
        }

    try:
        result = await _call_api(company_name)
        # 缓存结果
        _info_cache[company_name] = result
        return result
    except Exception as e:
        logger.error("工商 API 调用失败: %s", e)
        return {
            "companyName": company_name,
            "error": f"API 调用失败: {str(e)[:200]}",
        }


async def _call_api(company_name: str) -> dict:
    """调用腾讯云市场工商信息 API。"""
    endpoint = _normalize_endpoint(_endpoint)
    headers = _build_cloudmarket_headers()
    params = {"keyword": company_name}

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(endpoint, params=params, headers=headers) as resp:
            status = resp.status
            body = await resp.text()

            if status != 200:
                logger.warning("工商 API HTTP %d: %s", status, body[:300])
                return {
                    "companyName": company_name,
                    "error": _format_cloudmarket_error(status, body),
                }

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return {"companyName": company_name, "error": f"API 返回非 JSON: {body[:200]}"}

            return _normalize_response(company_name, data)


def _format_cloudmarket_error(status: int, body: str) -> str:
    """把云市场网关错误转换为可操作提示。"""
    message = body[:200]
    try:
        payload = json.loads(body)
        message = payload.get("message") or payload.get("msg") or message
    except json.JSONDecodeError:
        pass

    if 420 < status < 430:
        return (
            f"API 返回 HTTP {status}: {message}。请确认设置中填写的是该云市场 API 商品"
            "资源实例提供的 secretId/secretKey，并且已绑定有效使用计划；不要使用普通 CAM 云 API 密钥。"
        )
    if status in (411, 412, 413, 414):
        return f"API 返回 HTTP {status}: {message}。请检查云市场 API 网关鉴权参数。"
    return f"API 返回 HTTP {status}: {message}"


def _build_cloudmarket_headers() -> dict[str, str]:
    """按腾讯云云市场 API 网关用户端鉴权生成请求头。"""
    x_date = formatdate(usegmt=True)
    signing_str = f"x-date: {x_date}"
    signature = base64.b64encode(
        hmac.new(_secret_key.encode("utf-8"), signing_str.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")

    return {
        "Content-Type": "application/json",
        "Authorization": json.dumps({
            "id": _secret_id,
            "x-date": x_date,
            "signature": signature,
        }, ensure_ascii=False),
        "request-id": str(uuid.uuid4()),
    }


def _extract_api_entries(value, path: str = "") -> list[dict[str, str]]:
    """递归提取 API 返回里的所有非空叶子词条。"""
    entries: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            entries.extend(_extract_api_entries(child, next_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            entries.extend(_extract_api_entries(child, f"{path}[{index}]"))
    elif value is not None and str(value).strip():
        entries.append({"path": path, "label": path.split(".")[-1], "value": str(value).strip()})
    return entries


def _normalize_response(company_name: str, raw: dict) -> dict:
    """
    将 API 原始返回归一化为统一字段结构。
    兼容聚美智数/天眼查/企查查等不同供应商的字段命名。
    """
    def _is_success_code(value) -> bool:
        return value in (0, 200, "0", "200", "success", "SUCCESS", None)

    code = raw.get("code") or raw.get("Code") or raw.get("status") or raw.get("Status")
    if not _is_success_code(code):
        message = raw.get("message") or raw.get("msg") or raw.get("Message") or "工商 API 返回失败"
        return {"companyName": company_name, "error": f"{message} (code={code})", "raw": raw}

    # 有些 API 返回 {code, data: {...}} / {result: {...}} 格式
    data = raw.get("data") or raw.get("result") or raw

    if isinstance(data, dict) and data.get("code") in (0, 200, "0", "200"):
        data = data.get("data") or data.get("result") or data

    if not isinstance(data, dict):
        return {"companyName": company_name, "error": "工商 API 返回 data 格式异常", "raw": raw}

    nested_sources = [
        data.get("baseInfo"), data.get("basicInfo"), data.get("businessInfo"),
        data.get("Base"),
        data.get("enterprise"), data.get("company"), data.get("all"),
        data.get("detail"), data.get("result"),
    ]
    merged_data = dict(data)
    for nested in nested_sources:
        if isinstance(nested, dict):
            merged_data.update(nested)
    data = merged_data

    # 归一化字段（兼容多种供应商格式）
    def _get(*keys, default=""):
        for k in keys:
            v = data.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return default

    def _items(key: str) -> list:
        value = data.get(key) or []
        return value if isinstance(value, list) else []

    def _first_text(item: dict, *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    # 股东信息
    shareholders = []
    for item in (
        data.get("shareholders") or data.get("partnerList") or data.get("shareholderList")
        or data.get("holderList") or data.get("Partners") or []
    ):
        if isinstance(item, dict):
            name = (
                item.get("name") or item.get("stockholderName") or item.get("shareholderName")
                or item.get("partnerName") or item.get("StockName") or ""
            )
            if name:
                shareholders.append(name)
        elif isinstance(item, str) and item:
            shareholders.append(item)

    # 高管信息
    executives = []
    for item in (
        data.get("executives") or data.get("staffList") or data.get("employeeList")
        or data.get("mainStaff") or data.get("Employees") or []
    ):
        if isinstance(item, dict):
            name = item.get("name") or item.get("personName") or item.get("staffName") or item.get("EmployeeName") or ""
            title = item.get("title") or item.get("position") or item.get("job") or item.get("Position") or ""
            entry = f"{name}（{title}）" if title else name
            if name:
                executives.append(entry)
        elif isinstance(item, str) and item:
            executives.append(item)

    # 经营异常
    abnormal = []
    for item in (data.get("abnormalInfo") or data.get("abnormalList") or data.get("exceptionInfo") or data.get("Exceptions") or []):
        if isinstance(item, dict):
            reason = (
                item.get("reason") or item.get("abnormalReason") or item.get("includeReason")
                or item.get("AddReason") or item.get("Content") or ""
            )
            if reason:
                abnormal.append(reason)
        elif isinstance(item, str) and item:
            abnormal.append(item)

    # 行政处罚
    penalties = []
    for item in (data.get("penalties") or data.get("punishmentList") or data.get("administrativePenalty") or data.get("Penalties") or []):
        if isinstance(item, dict):
            reason = item.get("reason") or item.get("illegalType") or item.get("punishContent") or item.get("Content") or ""
            if reason:
                penalties.append(reason)
        elif isinstance(item, str) and item:
            penalties.append(item)

    websites = []
    contact_info = data.get("ContactInfo") if isinstance(data.get("ContactInfo"), dict) else {}
    for item in contact_info.get("Website") or []:
        if isinstance(item, dict):
            url = _first_text(item, "Url", "url")
            name = _first_text(item, "Name", "name")
            if url and name:
                websites.append(f"{name}：{url}")
            elif url:
                websites.append(url)

    changes = []
    for item in _items("Changes"):
        if isinstance(item, dict):
            field = _first_text(item, "ChangeField")
            date = _first_text(item, "ChangeDate")
            if field:
                changes.append(f"{date[:10]} {field}".strip())

    original_names = []
    for item in _items("OriginalName"):
        if isinstance(item, dict):
            name = _first_text(item, "Name")
            date = _first_text(item, "ChangeDate")
            if name:
                original_names.append(f"{name}（{date[:10]}）" if date else name)

    tax_credit_levels = []
    for item in _items("TaxCreditItems"):
        if isinstance(item, dict):
            year = _first_text(item, "Year")
            level = _first_text(item, "Level")
            if year or level:
                tax_credit_levels.append(f"{year}：{level}" if year and level else year or level)

    permissions = []
    for item in _items("Permissions"):
        if isinstance(item, dict):
            name = _first_text(item, "Name")
            if name:
                permissions.append(name)

    spot_checks = []
    for item in _items("SpotChecks"):
        if isinstance(item, dict):
            check_type = _first_text(item, "Type")
            consequence = _first_text(item, "Consequence")
            if check_type or consequence:
                spot_checks.append(f"{check_type}：{consequence}" if check_type and consequence else check_type or consequence)

    dishonest_items = [
        _first_text(item, "DisreputTypeName", "CaseCode", "CourtName")
        for item in _items("ShiXinItems") if isinstance(item, dict)
    ]
    dishonest_items = [item for item in dishonest_items if item]

    enforced_items = []
    for item in _items("ZhiXingItems"):
        if isinstance(item, dict):
            case_code = _first_text(item, "CaseCode")
            money = _first_text(item, "ExecMoney")
            if case_code or money:
                enforced_items.append(f"{case_code}（{money}）" if case_code and money else case_code or money)

    pledges = [_first_text(item, "RegistNo", "Status") for item in _items("Pledges") if isinstance(item, dict)]
    pledges = [item for item in pledges if item]
    movable_pledges = [_first_text(item, "RegisterNo", "Status") for item in _items("MPledges") if isinstance(item, dict)]
    movable_pledges = [item for item in movable_pledges if item]

    industry_info = data.get("Industry") if isinstance(data.get("Industry"), dict) else {}

    normalized_company = _get("companyName", "name", "entName", "enterpriseName", "CompanyName", default=company_name)
    unified_credit_code = _get("unifiedCreditCode", "creditCode", "creditNo", "socialCreditCode", "CreditNo")
    industry = _get("industry", "industryName", "belongIndustry") or _first_text(industry_info, "Industry")
    sub_industry = _first_text(industry_info, "SubIndustry")
    company_key = unified_credit_code or normalized_company or company_name

    return {
        "companyName": normalized_company,
        "sourceCompanyName": company_name,
        "companyKey": company_key,
        "legalRepresentative": _get("legalRepresentative", "legalPerson", "legalPersonName", "frName", "operName", "LegalPerson"),
        "registrationCapital": _get("registrationCapital", "regCapital", "registCapi", "registeredCapital", "Capital"),
        "paidInCapital": _get("paidInCapital", "paidCapital", "paidCapi"),
        "establishedDate": _get("establishedDate", "startDate", "esDate", "foundDate", "estiblishTime", "EstablishDate"),
        "businessStatus": _get("businessStatus", "regStatus", "openStatus", "status", "CompanyStatus"),
        "unifiedCreditCode": unified_credit_code,
        "registrationNumber": _get("registrationNumber", "regNo", "registrationNo", "CompanyCode"),
        "taxpayerId": _get("taxpayerId", "taxId"),
        "businessScope": _get("businessScope", "scope", "operatingScope", "BusinessScope"),
        "industry": industry,
        "subIndustry": sub_industry,
        "registeredIndustry": industry,
        "registeredSubIndustry": sub_industry,
        "address": _get("address", "regAddress", "addressName", "registeredAddress", "CompanyAddress"),
        "companyType": _get("companyType", "CompanyType"),
        "registrationAuthority": _get("registrationAuthority", "Authority"),
        "businessDateFrom": _get("businessDateFrom", "BusinessDateFrom"),
        "businessDateTo": _get("businessDateTo", "BusinessDateTo", "BusinessDateToStr"),
        "issueDate": _get("issueDate", "IssueDate"),
        "orgCode": _get("orgCode", "OrgCode"),
        "isOnStock": _get("isOnStock", "IsOnStock"),
        "stockNumber": _get("stockNumber", "StockNumber"),
        "stockType": _get("stockType", "StockType"),
        "revokeDate": _get("revokeDate", "RevokeDate"),
        "contactPhone": _first_text(contact_info, "PhoneNumber"),
        "contactEmail": _first_text(contact_info, "Email"),
        "websites": websites,
        "shareholders": shareholders,
        "executives": executives,
        "branchCount": len(data.get("branches") or data.get("branchList") or data.get("Branches") or []),
        "abnormalInfo": abnormal,
        "penalties": penalties,
        "changeCount": len(_items("Changes")),
        "changes": changes,
        "dishonestCount": len(_items("ShiXinItems")),
        "dishonestItems": dishonest_items,
        "enforcedCount": len(_items("ZhiXingItems")),
        "enforcedItems": enforced_items,
        "pledgeCount": len(_items("Pledges")),
        "pledges": pledges,
        "movablePledgeCount": len(_items("MPledges")),
        "movablePledges": movable_pledges,
        "originalNames": original_names,
        "taxCreditLevels": tax_credit_levels,
        "permissions": permissions,
        "spotChecks": spot_checks,
        "permissionCount": len(_items("Permissions")),
        "spotCheckCount": len(_items("SpotChecks")),
        "apiEntries": _extract_api_entries(raw.get("data") or raw.get("result") or raw),
        "annualReport": _get("annualReport", "annualReportStatus"),
        "raw": raw,
    }


async def test_connection() -> dict:
    """测试工商 API 连接是否有效。"""
    if not _secret_id or not _secret_key:
        return {"ok": False, "message": "未配置 SecretId 和 SecretKey"}

    try:
        result = await query_business_info("深圳市腾讯计算机系统有限公司")
        if result.get("error"):
            return {"ok": False, "message": result["error"]}
        company = result.get("companyName", "")
        legal = result.get("legalRepresentative", "")
        status = result.get("businessStatus", "")
        return {
            "ok": True,
            "message": f"连接成功: {company} | 法人: {legal} | 状态: {status}",
        }
    except Exception as e:
        return {"ok": False, "message": f"连接失败: {str(e)[:200]}"}


# ── 启动时加载配置 ──
_load_config()
