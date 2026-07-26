import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", minHeight: "100vh", padding: 40,
          fontFamily: "system-ui, sans-serif", color: "#333",
        }}>
          <h1 style={{ fontSize: 24, marginBottom: 12 }}>应用发生错误</h1>
          <p style={{ fontSize: 14, color: "#666", maxWidth: 500, textAlign: "center", marginBottom: 24 }}>
            {this.state.error?.message || "未知错误"}
          </p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            style={{
              padding: "10px 24px", fontSize: 14, borderRadius: 8,
              border: "none", background: "#3b82f6", color: "#fff", cursor: "pointer",
            }}
          >
            重新加载
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
