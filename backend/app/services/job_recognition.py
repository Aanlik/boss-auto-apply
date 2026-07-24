"""
岗位识别/归一化服务：从原始岗位数据中提取关键词、薪资结构、生成摘要。
"""
import re
from app.models.job import JobRecord


SKILL_POOL = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "React", "Vue", "Angular", "Next.js", "Node.js", "Django", "Flask",
    "FastAPI", "Spring Boot", "Express", "Redis", "MySQL", "PostgreSQL",
    "MongoDB", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git",
    "Linux", "SQL", "GraphQL", "REST", "gRPC", "Kafka", "RabbitMQ",
    "Spark", "Flink", "Hadoop", "TensorFlow", "PyTorch",
    "Webpack", "Vite", "HTML", "CSS", "Sass", "Tailwind",
]


def recognize_job(job: JobRecord) -> JobRecord:
    """对岗位执行识别：提取关键词、解析薪资、生成摘要。"""
    keywords = _extract_keywords(job.title, job.jd_text)
    salary_min, salary_max = _parse_salary(job.salary)
    summary = _generate_summary(job.title, job.company, job.city, job.salary, keywords)

    job.keywords = keywords
    job.salary_min = salary_min
    job.salary_max = salary_max
    job.structured_summary = summary
    return job


def _extract_keywords(title: str, jd_text: str) -> list[str]:
    text = f"{title} {jd_text}"
    found = []
    for skill in SKILL_POOL:
        if re.search(rf"(?<![a-zA-Z]){re.escape(skill)}(?![a-zA-Z])", text, re.IGNORECASE):
            found.append(skill)
    return found


def _parse_salary(salary: str) -> tuple[int, int]:
    """解析 '20-30K' 格式的薪资，返回 (min, max)。"""
    if not salary:
        return 0, 0
    match = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*[Kk]", salary)
    if match:
        return int(match.group(1)), int(match.group(2))
    single = re.search(r"(\d+)\s*[Kk]", salary)
    if single:
        v = int(single.group(1))
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
