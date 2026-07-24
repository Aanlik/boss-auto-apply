import { useState, useRef, useEffect } from "react";
import { chatWithAI } from "../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatPanelProps {
  step: "evaluate" | "analyze" | "optimize";
  context: unknown;
  profileName?: string;
  placeholder?: string;
  title?: string;
  onApply?: (messages: Message[]) => void;
}

export default function ChatPanel({
  step,
  context,
  profileName = "",
  placeholder = "输入你的问题...",
  title = "AI 对话",
  onApply,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [applying, setApplying] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  async function onSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);

    const userMsg: Message = { role: "user", content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);

    try {
      const { reply } = await chatWithAI({
        step,
        context,
        messages: updated,
        profile_name: profileName,
      });
      setMessages([...updated, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages([...updated, { role: "assistant", content: `❌ ${e instanceof Error ? e.message : "对话失败"}` }]);
    } finally {
      setSending(false);
    }
  }

  async function handleApply() {
    if (!onApply || messages.length === 0) return;
    setApplying(true);
    try {
      await onApply(messages);
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="chat-header__title">💬 {title}</span>
        <div style={{ display: "flex", gap: 8 }}>
          {onApply && messages.length > 0 && (
            <button type="button" className="button-primary" onClick={handleApply} disabled={applying} style={{ fontSize: 11, padding: '3px 10px' }}>
              {applying ? "应用中..." : "↑ 应用到上方"}
            </button>
          )}
          {messages.length > 0 && (
            <button type="button" className="chat-header__clear" onClick={() => setMessages([])}>
              清空
            </button>
          )}
        </div>
      </div>

      <div className="chat-list" ref={listRef}>
        {messages.length === 0 && (
          <p className="chat-empty">向 AI 提问，深入讨论这步的结果</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role === "user" ? "chat-msg--user" : "chat-msg--ai"}`}>
            <div className="chat-msg__bubble">{m.content}</div>
          </div>
        ))}
        {sending && (
          <div className="chat-msg chat-msg--ai">
            <div className="chat-msg__bubble chat-msg__bubble--typing">...</div>
          </div>
        )}
      </div>

      <div className="chat-input-row">
        <input
          className="form-input form-input--inline chat-input"
          type="text"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSend()}
          disabled={sending}
        />
        <button type="button" className="button-primary chat-send" onClick={onSend} disabled={sending || !input.trim()}>
          发送
        </button>
      </div>
    </div>
  );
}
