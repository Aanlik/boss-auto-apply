import asyncio
import json
import re

from app.services import business_info


def test_business_info_uses_shanghai_cloudmarket_endpoint_by_default():
    assert business_info.DEFAULT_ENDPOINT == (
        "https://ap-shanghai.cloudmarket-apigw.com/"
        "service-6dr7ul9n/enterprise/business/all"
    )


def test_business_info_normalizes_documented_http_https_endpoint():
    endpoint = business_info._normalize_endpoint(
        "http&https://ap-shanghai.cloudmarket-apigw.com/service-6dr7ul9n/enterprise/business/all"
    )

    assert endpoint == business_info.DEFAULT_ENDPOINT


def test_business_info_migrates_legacy_endpoint_to_cloudmarket():
    endpoint = business_info._normalize_endpoint("https://api.jumeiapi.com/business/info")

    assert endpoint == business_info.DEFAULT_ENDPOINT


def test_business_info_set_config_persists_normalized_endpoint(tmp_path, monkeypatch):
    config_file = tmp_path / "business_info_config.json"
    monkeypatch.setattr(business_info, "CONFIG_FILE", config_file)

    assert business_info.set_config(
        "sid",
        "skey",
        "http&https://ap-shanghai.cloudmarket-apigw.com/service-6dr7ul9n/enterprise/business/all",
    )

    saved = json.loads(config_file.read_text())
    assert saved["endpoint"] == business_info.DEFAULT_ENDPOINT


def test_business_info_calls_cloudmarket_with_post_query_keyword(monkeypatch):
    recorded = {}

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            return json.dumps({
                "code": 200,
                "data": {"baseInfo": {"name": "深圳市腾讯计算机系统有限公司"}},
            })

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, params=None, headers=None):
            recorded["endpoint"] = endpoint
            recorded["params"] = params
            recorded["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(business_info.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(
        business_info,
        "_endpoint",
        "http&https://ap-shanghai.cloudmarket-apigw.com/service-6dr7ul9n/enterprise/business/all",
    )
    monkeypatch.setattr(business_info, "_secret_id", "sid")
    monkeypatch.setattr(business_info, "_secret_key", "skey")

    result = asyncio.run(business_info._call_api("深圳市腾讯计算机系统有限公司"))

    assert recorded["endpoint"] == business_info.DEFAULT_ENDPOINT
    assert recorded["params"] == {"keyword": "深圳市腾讯计算机系统有限公司"}
    assert recorded["headers"]["Content-Type"] == "application/json"
    auth = json.loads(recorded["headers"]["Authorization"])
    assert auth["id"] == "sid"
    assert re.match(r"^[A-Za-z0-9+/]+={0,2}$", auth["signature"])
    assert auth["x-date"].endswith("GMT")
    assert "request-id" in recorded["headers"]
    assert result["companyName"] == "深圳市腾讯计算机系统有限公司"


def test_business_info_retries_transient_cloudmarket_failure(monkeypatch):
    attempts = 0

    class FakeResponse:
        def __init__(self, status):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            if self.status == 200:
                return json.dumps({"code": 200, "data": {"Base": {"CompanyName": "重试成功公司"}}})
            return "temporary failure"

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            return FakeResponse(503 if attempts < 3 else 200)

    monkeypatch.setattr(business_info.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(business_info, "_secret_id", "sid")
    monkeypatch.setattr(business_info, "_secret_key", "skey")

    result = asyncio.run(business_info._call_api("重试公司"))

    assert attempts == 3
    assert result["companyName"] == "重试成功公司"


def test_business_info_formats_use_plan_error():
    message = business_info._format_cloudmarket_error(
        421,
        '{"message":"在配置中使用计划不存在"}',
    )

    assert "使用计划" in message
    assert "云市场 API 商品" in message
    assert "普通 CAM 云 API 密钥" in message


def test_business_info_normalizes_cloudmarket_wrapped_response():
    normalized = business_info._normalize_response("腾讯", {
        "code": 200,
        "message": "success",
        "data": {
            "baseInfo": {
                "name": "深圳市腾讯计算机系统有限公司",
                "legalPersonName": "马化腾",
                "regCapital": "6500万人民币",
                "regStatus": "存续",
                "creditCode": "91440300708461136T",
                "scope": "计算机软硬件的技术开发",
            },
            "partnerList": [{"stockholderName": "深圳市世纪凯旋科技有限公司"}],
            "staffList": [{"personName": "马化腾", "position": "董事长"}],
        },
    })

    assert normalized["companyName"] == "深圳市腾讯计算机系统有限公司"
    assert normalized["sourceCompanyName"] == "腾讯"
    assert normalized["companyKey"] == "91440300708461136T"
    assert normalized["legalRepresentative"] == "马化腾"
    assert normalized["registrationCapital"] == "6500万人民币"
    assert normalized["businessStatus"] == "存续"
    assert normalized["unifiedCreditCode"] == "91440300708461136T"
    assert normalized["shareholders"] == ["深圳市世纪凯旋科技有限公司"]
    assert normalized["executives"] == ["马化腾（董事长）"]


def test_business_info_normalizes_cloudmarket_capitalized_sections():
    normalized = business_info._normalize_response("腾讯", {
        "code": 200,
        "data": {
            "Base": {
                "CompanyName": "深圳市腾讯计算机系统有限公司",
                "LegalPerson": "马化腾",
                "Capital": "6500.000000万人民币",
                "CompanyStatus": "存续（在营、开业、在册）",
                "CreditNo": "91440300708461136T",
                "BusinessScope": "计算机软硬件的技术开发",
                "CompanyAddress": "深圳市南山区腾讯大厦",
            },
            "Partners": [{"StockName": "张志东"}],
            "Employees": [{"EmployeeName": "刘华", "Position": "监事"}],
            "Penalties": [{"Content": "罚款人民币壹万元整"}],
            "Branches": [{"CompanyName": "南京分公司"}],
        },
    })

    assert normalized["companyName"] == "深圳市腾讯计算机系统有限公司"
    assert normalized["legalRepresentative"] == "马化腾"
    assert normalized["businessStatus"] == "存续（在营、开业、在册）"
    assert normalized["shareholders"] == ["张志东"]
    assert normalized["executives"] == ["刘华（监事）"]
    assert normalized["penalties"] == ["罚款人民币壹万元整"]
    assert normalized["branchCount"] == 1


def test_business_info_normalizes_full_enterprise_payload():
    normalized = business_info._normalize_response("杭州安那其", {
        "code": 200,
        "msg": "成功",
        "taskNo": "24734830306816485241",
        "data": {
            "Changes": [{"ChangeField": "住所变更", "ChangeDate": "2021-05-12 00:00:00"}],
            "ShiXinItems": [{"CaseCode": "失信案号", "DisreputTypeName": "有履行能力而拒不履行"}],
            "Branches": [{"CompanyName": "杭州安那其科技有限公司分公司"}],
            "Pledges": [{"RegistNo": "质押1", "Status": "有效"}],
            "Employees": [{"Position": "执行董事兼总经理", "EmployeeName": "薛梅"}],
            "OriginalName": [{"Name": "杭州旧名科技有限公司", "ChangeDate": "2019-01-01"}],
            "TaxCreditItems": [{"Year": "2024", "Level": "A"}],
            "Base": {
                "CompanyStatus": "存续",
                "BusinessScope": "一般项目：人工智能应用软件开发。",
                "Capital": "1000.000000万人民币",
                "CompanyType": "有限责任公司(自然人独资)",
                "LegalPerson": "薛梅",
                "EstablishDate": "2018-05-23 00:00:00",
                "CompanyAddress": "浙江省杭州市余杭区仓前街道龙泉路3号507室",
                "CompanyName": "杭州安那其科技有限公司",
                "OrgCode": "MA2CC1X50",
                "IsOnStock": "0",
                "CreditNo": "91330110MA2CC1X505",
                "CompanyCode": "330184000798156",
                "Authority": "杭州市余杭区市场监督管理局",
                "BusinessDateFrom": "2018-05-23 00:00:00",
                "BusinessDateTo": "9999-09-08 16:00:00",
            },
            "Industry": {"Industry": "信息传输、软件和信息技术服务业", "SubIndustry": "软件和信息技术服务业"},
            "Partners": [{"StockName": "薛梅", "StockPercent": "1.0000", "StockCapital": "1000"}],
            "Penalties": [{"Content": "罚款人民币壹万元整"}],
            "ZhiXingItems": [{"CaseCode": "执行案号", "ExecMoney": "10000"}],
            "Exceptions": [{"AddReason": "未按规定公示年度报告"}],
            "Permissions": [{"Name": "增值电信业务经营许可"}],
            "ContactInfo": {
                "Website": [{"Url": "www.jumdata.com", "Name": "聚美智数"}],
                "PhoneNumber": "057188382829",
                "Email": "hello@example.com",
            },
            "MPledges": [{"RegisterNo": "动产抵押1", "Status": "有效"}],
            "SpotChecks": [{"Type": "抽查", "Consequence": "未发现问题"}],
        },
    })

    assert normalized["companyName"] == "杭州安那其科技有限公司"
    assert normalized["companyKey"] == "91330110MA2CC1X505"
    assert normalized["registeredIndustry"] == "信息传输、软件和信息技术服务业"
    assert normalized["registeredSubIndustry"] == "软件和信息技术服务业"
    assert normalized["companyType"] == "有限责任公司(自然人独资)"
    assert normalized["registrationAuthority"] == "杭州市余杭区市场监督管理局"
    assert normalized["industry"] == "信息传输、软件和信息技术服务业"
    assert normalized["subIndustry"] == "软件和信息技术服务业"
    assert normalized["contactPhone"] == "057188382829"
    assert normalized["contactEmail"] == "hello@example.com"
    assert normalized["websites"] == ["聚美智数：www.jumdata.com"]
    assert normalized["changeCount"] == 1
    assert normalized["dishonestCount"] == 1
    assert normalized["enforcedCount"] == 1
    assert normalized["taxCreditLevels"] == ["2024：A"]
    assert normalized["permissions"] == ["增值电信业务经营许可"]
    entries = normalized["apiEntries"]
    entry_map = {entry["path"]: entry["value"] for entry in entries}
    assert entry_map["Base.CompanyName"] == "杭州安那其科技有限公司"
    assert entry_map["Industry.SubIndustry"] == "软件和信息技术服务业"
    assert entry_map["Partners[0].StockName"] == "薛梅"
    assert entry_map["ContactInfo.Website[0].Url"] == "www.jumdata.com"
    assert entry_map["Changes[0].ChangeField"] == "住所变更"
