import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_extract_detail_preserves_full_limited_company_name():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required to execute the detail extraction script")

    script_path = Path(__file__).parents[1] / "app" / "services" / "extract_detail.js"
    harness = f"""
const fs = require('fs');
global.location = {{ href: 'https://www.zhipin.com/job_detail/demo.html' }};
global.document = {{
  title: 'HRBP - 河南彭世健康管理集团',
  body: {{ innerText: '职位描述\\n岗位职责\\n负责团队管理' }},
  querySelectorAll(selector) {{
    if (selector.includes('business-info')) return [{{ innerText: '公司全称：河南彭世健康管理集团有限公司' }}];
    if (selector === '.job-detail-section') return [{{ innerText: '职位描述\\n岗位职责\\n负责团队管理' }}];
    return [];
  }},
  querySelector() {{ return null; }}
}};
const result = eval(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
process.stdout.write(result);
"""
    result = subprocess.run([node, "-e", harness], capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["company_name"] == "河南彭世健康管理集团有限公司"
