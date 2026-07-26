import type { ReactNode } from "react";

// ── 空态 ──
export function EmptyState({ icon = "📋", title, desc, action }: {
  icon?: string;
  title: string;
  desc?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">{icon}</div>
      <p className="empty-state__title">{title}</p>
      {desc && <p className="empty-state__desc">{desc}</p>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  );
}

// ── 错误横幅 ──
export function ErrorBanner({ message, onRetry, onDismiss }: {
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}) {
  return (
    <div className="panel panel-strong" style={{ borderColor: "var(--danger)", marginBottom: 12 }}>
      <div className="panel-inner" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 16 }}>⚠️</span>
          <span style={{ fontSize: 13, color: "var(--danger)" }}>{message}</span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {onRetry && (
            <button type="button" className="button-secondary" onClick={onRetry} style={{ fontSize: 12 }}>
              重试
            </button>
          )}
          {onDismiss && (
            <button type="button" className="button-quiet" onClick={onDismiss} style={{ fontSize: 12 }}>
              关闭
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 加载指示器 ──
export function Spinner({ text = "加载中..." }: { text?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 12, color: "var(--text-muted)", fontSize: 13 }}>
      <span className="spinner" />
      {text}
    </div>
  );
}
