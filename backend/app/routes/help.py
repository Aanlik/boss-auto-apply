from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/api/help", tags=["help"])


@router.get("/center")
def help_center() -> dict:
    modules = [
        {
            "key": "dashboard",
            "label": "仪表盘",
            "purpose": "查看全流程进度、待办、质量问题和下一步建议。流程引导、质量体检和 CRM 统计当前已选岗位；趋势和漏斗会标明全库历史。",
            "whenToUse": ["每天开始求职前", "不确定下一步该处理什么时", "上线前做整体巡检时"],
            "nextStep": "先确认卡片是全库历史还是当前已选岗位，再进入对应模块处理。",
            "steps": ["查看全流程状态条是否有失败或阻塞", "确认流程引导和质量卡片的当前已选岗位范围", "按下一步建议进入岗位、尽调、排序或打招呼模块", "处理完成后回到仪表盘确认对应范围的状态恢复"],
            "goodSignals": ["关键任务没有失败状态", "岗位、尽调、排序、发送都有明确进度", "质量板块没有高优先级缺口"],
            "commonFailures": ["岗位池为空", "存在失败任务", "流程状态长时间未刷新"],
            "safetyNotes": ["仪表盘只做总览和导航，具体删除、发送、清理仍需要到对应模块确认。"],
            "repairActions": [
                {"label": "刷新全流程状态", "page": "dashboard", "type": "refresh"},
                {"label": "查看失败恢复中心", "page": "dashboard", "type": "navigate"},
            ],
        },
        {
            "key": "resumes",
            "label": "简历",
            "purpose": "解析简历、优化内容、生成 PDF，并沉淀版本对比。",
            "whenToUse": ["新增或更新简历后", "准备针对某类岗位生成投递版本时", "PDF 下载或排版异常时"],
            "nextStep": "先上传或确认当前简历，再针对目标岗位生成优化和 PDF。",
            "steps": ["上传简历并检查字段识别结果", "选择目标岗位类型生成优化建议", "预览 PDF 后再下载或进入投递流程"],
            "goodSignals": ["核心经历、项目、技能字段完整", "PDF 预览无重叠和截断", "版本记录能追溯到生成时间和目标岗位"],
            "commonFailures": ["PDF 生成失败", "简历字段缺失", "优化结果过于泛化"],
            "safetyNotes": ["导出或分享前先确认隐私信息是否需要脱敏。"],
            "repairActions": [
                {"label": "补齐简历字段", "page": "resumes", "type": "navigate"},
                {"label": "预览 PDF 简历", "page": "resumes", "type": "navigate"},
            ],
        },
        {
            "key": "jobs",
            "label": "岗位",
            "purpose": "抓取、导入、筛选、补齐 JD，并维护黑名单和岗位状态。",
            "whenToUse": ["开始一轮岗位收集时", "需要批量补齐 JD 或清理重复岗位时", "维护企业黑名单时"],
            "nextStep": "先确认 BOSS 登录和筛选条件，再抓取或导入岗位，最后补齐 JD。",
            "steps": ["检查 BOSS 登录状态和筛选条件", "抓取或导入岗位后查看岗位池质量", "补齐 JD、处理重复岗位、确认黑名单过滤结果"],
            "goodSignals": ["岗位有来源链接和抓取时间", "JD 缺失数量持续下降", "重复岗位被合并且保留最新状态"],
            "commonFailures": ["BOSS 未登录或 Cookie 失效", "JD 缺失", "岗位重复", "黑名单过滤后岗位消失"],
            "safetyNotes": ["黑名单删除后岗位可能重新显示，删除前先确认是否只是临时误加。"],
            "repairActions": [
                {"label": "检查 BOSS 登录", "page": "jobs", "type": "navigate"},
                {"label": "下载导入模板", "page": "settings", "type": "download", "endpoint": "/api/jobs/import-wizard/template"},
                {"label": "查看岗位池质量", "page": "jobs", "type": "navigate"},
            ],
        },
        {
            "key": "diligence",
            "label": "尽调",
            "purpose": "整合工商 API、搜索证据和 AI 分析，判断公司风险与行业趋势。",
            "whenToUse": ["岗位进入重点候选池后", "公司名称疑似简称或别名时", "排序前需要补风险证据时"],
            "nextStep": "优先对推荐岗位公司做一键尽调，再复核工商名称和风险证据。",
            "steps": ["先确认岗位企业名是否已经替换为工商注册名", "执行一键尽调或只刷新工商/搜索证据", "查看风险、行业趋势和证据更新时间"],
            "goodSignals": ["工商名称、统一社会信用代码和行业信息完整", "搜索证据有来源和刷新时间", "AI 行业分析明确给出优势、劣势和关注点"],
            "commonFailures": ["工商 API 配置错误", "搜索证据不足", "公司名称不一致"],
            "safetyNotes": ["尽调分数是辅助判断，遇到法律、征信或劳动争议信息应回到证据源复核。"],
            "repairActions": [
                {"label": "配置工商 API", "page": "settings", "type": "navigate"},
                {"label": "配置百度搜索", "page": "settings", "type": "navigate"},
                {"label": "只刷新工商/搜索证据", "page": "diligence", "type": "navigate"},
            ],
        },
        {
            "key": "ranking",
            "label": "排序",
            "purpose": "把简历匹配、公司风险、求职偏好和 JD 质量合并成优先级。",
            "whenToUse": ["岗位和尽调信息基本齐全后", "需要决定当天优先沟通哪些岗位时", "想按风险或匹配度调整偏好时"],
            "nextStep": "先确认岗位已补 JD、公司已尽调，再选择权重模板生成排序。",
            "steps": ["筛出当前要比较的岗位", "选择或调整权重模板", "查看排序解释并把合适岗位推进打招呼"],
            "goodSignals": ["排序结果能解释匹配、风险和偏好来源", "被取消勾选的岗位不会进入排序", "权重模板与当前求职策略一致"],
            "commonFailures": ["没有可排序岗位", "权重不符合当前求职目标", "排序解释不充分"],
            "safetyNotes": ["排序只代表当前数据下的建议，JD 缺失或尽调过期会影响结果。"],
            "repairActions": [
                {"label": "补齐 JD", "page": "jobs", "type": "navigate"},
                {"label": "完成尽调", "page": "diligence", "type": "navigate"},
                {"label": "调整排序权重", "page": "ranking", "type": "navigate"},
            ],
        },
        {
            "key": "greeting",
            "label": "打招呼",
            "purpose": "生成、校验、人工确认或灰度自动发送招呼语，并复盘回复。",
            "whenToUse": ["排序后准备触达岗位时", "需要批量生成但仍想保留确认权时", "自动发送前做页面可用性检查时"],
            "nextStep": "先生成招呼语草稿，通过校验和最终确认后，再人工或灰度发送。",
            "steps": ["生成候选话术", "查看校验和页面可用性", "小批量灰度发送并复盘回复率"],
            "goodSignals": ["每条话术都有岗位相关理由", "自动发送开关默认关闭且有批量上限", "失败原因能定位到登录、风控、页面或网络"],
            "commonFailures": ["话术校验失败", "页面风控", "找不到立即沟通按钮", "未先通过灰度首发"],
            "safetyNotes": ["自动发送不绕过验证码和风控，出现风险提示时应暂停并人工处理。"],
            "repairActions": [
                {"label": "发送前预检", "page": "greeting", "type": "navigate"},
                {"label": "检查页面可用性", "page": "greeting", "type": "navigate"},
            ],
        },
        {
            "key": "settings",
            "label": "设置与维护",
            "purpose": "维护 API 配置、岗位导入、求职偏好、配置备份和本机页面数据。",
            "whenToUse": ["首次配置系统时", "接口失败或数据异常时", "上线前或大批量操作前"],
            "nextStep": "首次使用先完成 API 配置和求职偏好，大批量操作前导出脱敏配置备份。",
            "steps": ["检查 AI、百度和工商 API 配置", "配置求职偏好", "导出配置备份或导入岗位模板"],
            "goodSignals": ["API 配置连接测试通过", "求职偏好已保存", "CSV 模板可以下载并预览导入"],
            "commonFailures": ["API Key 未配置", "连接测试失败", "导入数据字段缺失"],
            "safetyNotes": ["完整配置备份包含密钥，只保存在可信位置。"],
            "repairActions": [
                {"label": "打开设置", "page": "settings", "type": "navigate"},
                {"label": "导出脱敏配置", "page": "settings", "type": "navigate"},
                {"label": "下载岗位模板", "page": "settings", "type": "download", "endpoint": "/api/jobs/import-wizard/template"},
            ],
        },
    ]
    return {
        "kind": "help_center",
        "version": 1,
        "quickStart": [
            {"label": "先看仪表盘下一步", "page": "dashboard"},
            {"label": "补岗位和 JD", "page": "jobs"},
            {"label": "完成尽调与排序", "page": "diligence"},
            {"label": "发送前先预检", "page": "greeting"},
        ],
        "modules": modules,
        "principles": [
            "真实自动发送必须先灰度验证，不绕过验证码或风控。",
            "大批量操作前优先导出脱敏配置和岗位数据。",
            "遇到失败先看仪表盘任务状态，再进入对应模块处理。",
        ],
        "faq": [
            {"question": "为什么抓取或发送前总提示未登录？", "answer": "通常是 Cookie 失效、页面跳转到登录页或触发风控。先回到岗位或打招呼模块检查登录状态，再小批量重试。", "page": "jobs"},
            {"question": "什么时候可以开启自动发送？", "answer": "建议先完成话术校验、页面可用性检查和小批量灰度首发，确认失败率和回复情况正常后再扩大范围。", "page": "greeting"},
            {"question": "尽调分数可以直接决定是否投递吗？", "answer": "不建议单独使用分数决策。应结合工商信息、搜索证据、岗位匹配度和个人偏好一起判断。", "page": "diligence"},
            {"question": "上线前最少要检查哪些内容？", "answer": "至少完成前后端测试、生产构建、核心页面浏览器验收、BOSS 登录状态检查和配置备份确认。", "page": "settings"},
        ],
        "glossary": [
            {"term": "灰度模式", "meaning": "先用小批量、低频率验证真实发送链路，再逐步扩大范围。"},
            {"term": "一键尽调", "meaning": "对岗位公司同时刷新工商信息、搜索证据和 AI 风险分析。"},
            {"term": "岗位池质量", "meaning": "用于查看 JD 缺失、重复、过期、黑名单命中等影响后续流程的问题。"},
            {"term": "配置备份", "meaning": "导出 AI、搜索和工商接口配置，脱敏备份适合留档，完整备份需要妥善保管。"},
        ],
    }
