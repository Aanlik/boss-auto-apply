"""
岗位识别/归一化服务：从原始岗位数据中提取关键词、薪资结构、生成摘要。
"""
import re
from app.models.job import JobRecord


SKILL_POOL = [
    # 编程语言 / 框架
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "React", "Vue", "Angular", "Next.js", "Node.js", "Django", "Flask",
    "FastAPI", "Spring Boot", "Express", "Redis", "MySQL", "PostgreSQL",
    "MongoDB", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git",
    "Linux", "SQL", "GraphQL", "REST", "gRPC", "Kafka", "RabbitMQ",
    "Spark", "Flink", "Hadoop", "TensorFlow", "PyTorch",
    "Webpack", "Vite", "HTML", "CSS", "Sass", "Tailwind",
    # 非技术通用技能
    "产品设计", "用户研究", "数据分析", "项目管理", "团队管理",
    "市场营销", "品牌策划", "内容运营", "新媒体", "社群运营",
    "客户管理", "销售管理", "商务谈判", "财务分析", "人力资源",
    "招聘", "培训", "绩效考核", "法务", "合规",
    "敏捷开发", "Scrum", "OKR", "KPI",
    "Photoshop", "Figma", "Sketch", "Illustrator",
    "Excel", "PPT", "Word", "Power BI", "Tableau",
]


def recognize_job(job: JobRecord) -> JobRecord:
    """对岗位执行识别：提取关键词、解析薪资、生成摘要。"""
    keywords = _merge_keywords(job.keywords, _extract_keywords(job.title, job.jd_text))
    salary_min, salary_max = _parse_salary(job.salary)
    summary = _generate_summary(job.title, job.company, job.city, job.salary, keywords)

    job.keywords = keywords
    job.salary_min = salary_min
    job.salary_max = salary_max
    job.structured_summary = summary
    return job


def _merge_keywords(existing: list[str], extracted: list[str]) -> list[str]:
    merged: list[str] = []
    seen = set()
    for keyword in [*(existing or []), *(extracted or [])]:
        clean = str(keyword).strip()
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        merged.append(clean)
    return merged


def _extract_keywords(title: str, jd_text: str) -> list[str]:
    text = f"{title} {jd_text}"
    found = []
    for skill in SKILL_POOL:
        if re.search(rf"(?<![a-zA-Z]){re.escape(skill)}(?![a-zA-Z])", text, re.IGNORECASE):
            found.append(skill)
    return found


def _parse_salary(salary: str) -> tuple[int, int]:
    """解析多种薪资格式，返回 (min, max) K。"""
    if not salary or not salary.strip():
        return 0, 0
    s = salary.strip()
    # 格式1: "20-30K" / "20k-30k" / "20~30K"
    match = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*[Kk]", s)
    if match:
        return int(match.group(1)), int(match.group(2))
    # 格式2: "15K·16薪" (取整月薪资)
    match = re.search(r"(\d+)\s*[Kk]", s)
    if match:
        v = int(match.group(1))
        return v, v
    # 格式3: "8000-12000元/月" (转K)
    match = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*元\s*/", s)
    if match:
        return int(match.group(1)) // 1000, int(match.group(2)) // 1000
    # 格式4: "年薪20-30万"
    match = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*万", s)
    if match:
        return int(match.group(1)) * 10000 // 12000, int(match.group(2)) * 10000 // 12000
    # 格式5: "20K以上" / "30K起"
    match = re.search(r"(\d+)\s*[Kk]\s*(以上|起)", s)
    if match:
        v = int(match.group(1))
        return v, v * 2
    # 格式6: "面议" / "薪资open"
    if "面议" in s or "open" in s.lower():
        return 0, 0
    # 格式7: 纯数字 "20000" (可能是月薪元，转K)
    match = re.search(r"^(\d{4,6})$", s)
    if match:
        v = int(match.group(1)) // 1000
        return v, v
    return 0, 0


def _generate_summary(title: str, company: str, city: str, salary: str, keywords: list[str]) -> str:
    parts = [f"{company}·{title}"]
    if city:
        parts.append(city)
    if salary:
        parts.append(salary)
    base = " | ".join(parts)
    if keywords:
        key_str = "、".join(keywords[:5])
        return f"{base} | 技术栈: {key_str}"
    return base
