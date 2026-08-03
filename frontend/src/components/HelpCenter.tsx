import { useCallback, useEffect, useState } from "react";
import { getHelpCenter } from "../lib/api";
import type { HelpCenter as HelpCenterData } from "../lib/types";

const FALLBACK_HELP_CENTER: HelpCenterData = {
  kind: "help_center",
  version: 2,
  quickStart: [
    { label: "先看仪表盘下一步", page: "dashboard" },
    { label: "补岗位和 JD", page: "jobs" },
    { label: "完成尽调与排序", page: "diligence" },
    { label: "发送前先预检", page: "greeting" },
  ],
  modules: [
    {
      key: "dashboard",
      label: "仪表盘",
      purpose: "查看全流程进度、待办、质量问题和下一步建议。",
      whenToUse: ["每天开始求职前", "不确定下一步该处理什么时"],
      nextStep: "顶部为全库状态；流程引导、质量体检和 CRM 仅统计当前已选岗位，进入模块时以卡片的范围标记为准。",
      steps: ["先确认卡片是全库历史还是当前已选岗位", "处理阻塞和失败任务", "回到仪表盘确认对应范围的状态恢复"],
      goodSignals: ["关键任务没有失败状态", "质量板块没有高优先级缺口"],
      commonFailures: ["岗位池为空", "存在失败任务", "流程状态长时间未刷新"],
      safetyNotes: ["具体删除、发送、清理仍需要到对应模块确认。"],
      repairActions: [{ label: "刷新全流程状态", page: "dashboard", type: "refresh" }],
    },
    {
      key: "jobs",
      label: "岗位",
      purpose: "抓取、导入、筛选、补齐 JD，并维护黑名单和岗位状态。",
      whenToUse: ["开始一轮岗位收集时", "需要批量补齐 JD 时"],
      nextStep: "先确认 BOSS 登录和筛选条件，再抓取或导入岗位，最后补齐 JD。",
      steps: ["检查 BOSS 登录", "抓取或导入岗位", "补齐 JD 并处理重复岗位"],
      goodSignals: ["岗位有来源链接和抓取时间", "JD 缺失数量持续下降"],
      commonFailures: ["BOSS 未登录或 Cookie 失效", "JD 缺失", "岗位重复"],
      safetyNotes: ["黑名单删除后岗位可能重新显示。"],
      repairActions: [{ label: "检查 BOSS 登录", page: "jobs", type: "navigate" }],
    },
    {
      key: "diligence",
      label: "尽调",
      purpose: "整合工商 API、搜索证据和 AI 分析，判断公司风险与行业趋势。",
      whenToUse: ["岗位进入重点候选池后", "排序前需要补风险证据时"],
      nextStep: "优先对推荐岗位公司做公司尽调，再复核工商名称和风险证据。",
      steps: ["确认工商注册名", "刷新工商和搜索证据", "查看风险和行业趋势"],
      goodSignals: ["工商字段完整", "证据有来源和刷新时间"],
      commonFailures: ["工商 API 配置错误", "搜索证据不足", "公司名称不一致"],
      safetyNotes: ["尽调分数是辅助判断，应回到证据源复核关键风险。"],
      repairActions: [{ label: "配置工商 API", page: "settings", type: "navigate" }],
    },
    {
      key: "ranking",
      label: "排序",
      purpose: "把简历匹配、公司风险、求职偏好和 JD 质量合并成优先级。",
      whenToUse: ["岗位和尽调信息基本齐全后", "决定当天优先沟通哪些岗位时"],
      nextStep: "先确认岗位已补 JD、公司已尽调，再选择权重模板生成排序。",
      steps: ["筛出要比较的岗位", "选择或调整权重模板", "查看排序解释"],
      goodSignals: ["排序解释清晰", "被取消勾选的岗位不会进入排序"],
      commonFailures: ["没有可排序岗位", "权重不符合当前求职目标"],
      safetyNotes: ["JD 缺失或尽调过期会影响排序结果。"],
      repairActions: [{ label: "调整排序权重", page: "ranking", type: "navigate" }],
    },
    {
      key: "greeting",
      label: "打招呼",
      purpose: "生成、校验、人工确认或灰度自动发送招呼语，并复盘回复。",
      whenToUse: ["排序后准备触达岗位时", "自动发送前做页面检查时"],
      nextStep: "先生成招呼语草稿，通过校验和最终确认后，再人工或灰度发送。发送前必须通过 BOSS 登录预检。",
      steps: ["生成话术草稿", "验证 BOSS 登录并查看校验结果", "小批量灰度发送"],
      goodSignals: ["话术有岗位相关理由", "失败原因能明确定位"],
      commonFailures: ["话术校验失败", "页面风控", "找不到立即沟通按钮", "连续失败后自动发送按钮变灰"],
      safetyNotes: ["自动发送不绕过验证码和风控。", "连续失败达到安全阈值后会锁定自动发送；先完成预检，再手动成功发送 1 个岗位，并在该岗位卡片点击“标记已招呼”后刷新安全阈值。"],
      repairActions: [
        { label: "发送前预检", page: "greeting", type: "navigate" },
        { label: "检测页面可用性", page: "greeting", type: "navigate" },
      ],
    },
    {
      key: "settings",
      label: "设置与维护",
      purpose: "维护 API 配置、导入岗位、求职偏好和配置备份。",
      whenToUse: ["首次配置系统时", "接口失败或数据异常时"],
      nextStep: "首次使用先完成 API 配置，再导入岗位开始求职流程。",
      steps: ["检查 AI、百度、工商 API 配置", "配置求职偏好", "导出配置备份"],
      goodSignals: ["API 配置连接测试通过", "求职偏好已保存"],
      commonFailures: ["API Key 未配置", "连接测试失败"],
      safetyNotes: ["完整配置备份包含密钥，请妥善保管。"],
      repairActions: [{ label: "打开设置", page: "settings", type: "navigate" }],
    },
  ],
  principles: [
    "发送前必须通过 BOSS 登录预检和灰度验证，不绕过验证码或风控。",
    "配置备份建议定期导出，避免密钥丢失。",
    "遇到失败先检查 API 配置和网络连接，再进入对应模块处理。",
  ],
  faq: [
    { question: "为什么帮助一直加载？", answer: "通常是后端未重启、接口暂时不可用或请求被代理到旧服务。可先使用内置帮助并点击重试。", page: "settings" },
    { question: "什么时候可以开启自动发送？", answer: "建议先完成话术校验、页面可用性检查和小批量灰度首发。", page: "greeting" },
    { question: "自动打招呼按钮为什么变灰，怎么恢复？", answer: "通常是连续发送失败触发安全阈值。先运行“发送前预检”和“检测页面可用性”，确认 BOSS 登录、风控和页面控件正常；再在 BOSS 手动成功发送 1 个岗位，回到该岗位卡片点击“标记已招呼”，最后点击“刷新安全阈值”。不要把未实际发送的岗位标记为成功，也不要直接编辑本地发送记录。", page: "greeting" },
  ],
  glossary: [
    { term: "灰度模式", meaning: "先用小批量、低频率验证真实发送链路，再逐步扩大范围。" },
    { term: "岗位池质量", meaning: "用于查看 JD 缺失、重复、过期、黑名单命中等影响后续流程的问题。" },
    { term: "安全阈值锁定", meaning: "连续发送失败后系统暂时禁用自动发送，需先完成预检并确认一次真实成功发送，再恢复批量操作。" },
  ],
};

export default function HelpCenter({
  show,
  onClose,
  onNavigate,
}: {
  show: boolean;
  onClose: () => void;
  onNavigate: (page: string) => void;
}) {
  const [data, setData] = useState<HelpCenterData | null>(null);
  const [activeKey, setActiveKey] = useState("dashboard");
  const [loadError, setLoadError] = useState("");

  const loadHelp = useCallback(() => {
    setLoadError("");
    getHelpCenter()
      .then(result => {
        setData(result);
        setActiveKey(result.modules[0]?.key || "dashboard");
      })
      .catch(error => {
        setData(FALLBACK_HELP_CENTER);
        setActiveKey(FALLBACK_HELP_CENTER.modules[0]?.key || "dashboard");
        setLoadError(error instanceof Error ? error.message : "帮助接口暂时不可用");
      });
  }, []);

  useEffect(() => {
    if (!show) return;
    loadHelp();
  }, [show, loadHelp]);

  if (!show) return null;
  const active = data?.modules.find(item => item.key === activeKey) || data?.modules[0];

  function runAction(page: string) {
    if (page === "settings") {
      onNavigate("settings");
    } else {
      onNavigate(page);
    }
    onClose();
  }

  return (
    <section className="settings-overlay" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="help-panel" onClick={event => event.stopPropagation()}>
        <div className="page-section__top">
          <div>
            <div className="page-kicker">帮助中心</div>
            <h2 className="page-title">遇到问题，先看这里</h2>
          </div>
          <button type="button" className="button-quiet" onClick={onClose} style={{ fontSize: 18, padding: "4px 8px" }}>✕</button>
        </div>

        {!data && <p className="settings-status">帮助内容加载中...</p>}
        {data && (
          <>
            {loadError && (
              <div className="help-alert">
                <div>
                  <strong>帮助内容使用内置版本</strong>
                  <span>接口暂时没有返回最新内容：{loadError}</span>
                </div>
                <button type="button" className="button-secondary button-secondary--sm" onClick={loadHelp}>重试加载</button>
              </div>
            )}
            <div className="help-quickstart">
              {data.quickStart.map(item => (
                <button key={item.label} type="button" className="button-secondary button-secondary--sm" onClick={() => runAction(item.page)}>
                  {item.label}
                </button>
              ))}
            </div>
            <div className="help-layout">
              <div className="help-tabs">
                {data.modules.map(module => (
                  <button key={module.key} type="button" className={module.key === activeKey ? "help-tab help-tab--active" : "help-tab"} onClick={() => setActiveKey(module.key)}>
                    {module.label}
                  </button>
                ))}
              </div>
              {active && (
                <div className="help-content">
                  <strong>{active.label}</strong>
                  <p>{active.purpose}</p>
                  <div className="help-block">
                    <span>什么时候用</span>
                    <div className="tag-row">
                      {active.whenToUse.map(item => <em key={item} className="tag tag--muted">{item}</em>)}
                    </div>
                  </div>
                  <div className="help-block">
                    <span>下一步</span>
                    <p>{active.nextStep}</p>
                  </div>
                  <div className="help-block">
                    <span>推荐步骤</span>
                    <ol className="help-list">
                      {active.steps.map(item => <li key={item}>{item}</li>)}
                    </ol>
                  </div>
                  <div className="help-block">
                    <span>完成信号</span>
                    <ul className="help-list">
                      {active.goodSignals.map(item => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                  <div className="help-block">
                    <span>常见失败</span>
                    <div className="tag-row">
                      {active.commonFailures.map(item => <em key={item} className="tag tag--muted">{item}</em>)}
                    </div>
                  </div>
                  <div className="help-block">
                    <span>安全提醒</span>
                    <ul className="help-list">
                      {active.safetyNotes.map(item => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                  <div className="help-block">
                    <span>修复动作</span>
                    <div className="toolbar-row toolbar-row--wrap">
                      {active.repairActions.map(action => (
                        <button key={action.label} type="button" className="button-secondary button-secondary--sm" onClick={() => runAction(action.page)}>
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="help-reference-grid">
              <div className="help-reference-card">
                <strong>常见问题</strong>
                <div className="help-faq-list">
                  {data.faq.map(item => (
                    <button key={item.question} type="button" className="help-faq-item" onClick={() => runAction(item.page)}>
                      <span>{item.question}</span>
                      <p>{item.answer}</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="help-reference-card">
                <strong>术语解释</strong>
                <div className="help-glossary">
                  {data.glossary.map(item => (
                    <span key={item.term}>
                      <b>{item.term}</b>
                      {item.meaning}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="help-principles">
              {data.principles.map(item => <span key={item}>{item}</span>)}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
