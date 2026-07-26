"""BOSS 抓取前筛选项。"""
from __future__ import annotations


FILTER_OPTIONS = {
    "scale": [
        ("0-20人", "301"), ("20-99人", "302"), ("100-499人", "303"),
        ("500-999人", "304"), ("1000-9999人", "305"), ("10000人以上", "306"),
    ],
    "stage": [
        ("未融资", "801"), ("天使轮", "802"), ("A轮", "803"), ("B轮", "804"),
        ("C轮", "805"), ("D轮及以上", "806"), ("已上市", "807"), ("不需要融资", "808"),
    ],
    "salary": [
        ("不限", "0"), ("3K以下", "402"), ("3-5K", "403"), ("5-10K", "404"),
        ("10-20K", "405"), ("20-50K", "406"), ("50K以上", "407"),
    ],
    "experience": [
        ("不限", "0"), ("在校生", "108"), ("应届生", "102"), ("经验不限", "101"),
        ("1年以内", "103"), ("1-3年", "104"), ("3-5年", "105"),
        ("5-10年", "106"), ("10年以上", "107"),
    ],
    "degree": [
        ("不限", "0"), ("初中及以下", "209"), ("中专/中技", "208"), ("高中", "206"),
        ("大专", "202"), ("本科", "203"), ("硕士", "204"), ("博士", "205"),
    ],
    "industry": [
        ("互联网", "1001"), ("电子商务", "1002"), ("金融", "1003"), ("游戏", "1004"),
        ("企业服务", "1005"), ("教育培训", "1006"), ("社交网络", "1007"),
        ("医疗健康", "1008"), ("生活服务", "1009"), ("广告营销", "1010"),
    ],
}


def list_filter_options() -> dict[str, list[dict[str, str]]]:
    return {
        key: [{"label": label, "value": value} for label, value in values]
        for key, values in FILTER_OPTIONS.items()
    }


def normalize_capture_filters(filters: dict | None) -> dict[str, str]:
    normalized = {}
    if not isinstance(filters, dict):
        return normalized
    allowed_values = {
        key: {value for _, value in values}
        for key, values in FILTER_OPTIONS.items()
    }
    for key, values in allowed_values.items():
        value = str(filters.get(key, "") or "").strip()
        if value and value != "0" and value in values:
            normalized[key] = value
    return normalized
