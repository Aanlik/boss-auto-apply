import { useState } from "react";
import { saveAiFeedback } from "../lib/api";
import type { AiFeedbackDomain } from "../lib/types";

export default function AiFeedbackButtons({
  domain,
  targetId,
  context,
  compact = false,
}: {
  domain: AiFeedbackDomain;
  targetId: string;
  context?: Record<string, unknown>;
  compact?: boolean;
}) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(useful: boolean) {
    if (!targetId || busy) return;
    setBusy(true);
    try {
      await saveAiFeedback({ domain, targetId, useful, context });
      setStatus(useful ? "已记录有用" : "已记录需改");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "反馈保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`ai-feedback ${compact ? "ai-feedback--compact" : ""}`} aria-label="AI 结果反馈">
      <span>这条结果</span>
      <button type="button" className="button-quiet button-secondary--sm" disabled={busy} onClick={() => send(true)}>有用</button>
      <button type="button" className="button-quiet button-secondary--sm" disabled={busy} onClick={() => send(false)}>需改</button>
      {status && <small>{status}</small>}
    </div>
  );
}
