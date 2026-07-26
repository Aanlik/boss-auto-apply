import { useState, useRef, useEffect } from "react";
import { chatWithAI, saveChatMessages, loadChatMessages } from "../lib/api";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";

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
  /** 持久化 key — 相同 key 的对话在 Store 中自动持久化，刷新不丢失 */
  chatKey?: string;
}

// 一次性迁移：将旧 localStorage chat-* 数据迁入 Store
function migrateLegacy(key: string): Message[] | null {
  try {
    const raw = localStorage.getItem(`chat-${key}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Array<{role: string; content: string}>;
    localStorage.removeItem(`chat-${key}`);
    if (!Array.isArray(parsed)) return null;
    return parsed.filter(m => m.role === "user" || m.role === "assistant") as Message[];
  } catch { return null; }
}

export default function ChatPanel({
  step, context, profileName = "",
  placeholder = "输入你的问题...", title = "AI 对话",
  onApply, chatKey,
}: ChatPanelProps) {
  const storeChatMessages = useWorkflowState().chatMessages;
  const dispatch = useWorkflowDispatch();


  const [messages, setMessages] = useState<Message[]>(() => {
    if (!chatKey) return [];
    // 优先从 Store 读取
    if (storeChatMessages[chatKey]) {
      const msgs = storeChatMessages[chatKey] as Message[];
      return msgs.filter(m => m.role === "user" || m.role === "assistant");
    }
    // 其次从旧 localStorage 迁移
    const legacy = migrateLegacy(chatKey);
    return legacy || [];
  });

  // 挂载时从后端加载（仅在 Store 和 localStorage 均为空时）
  useEffect(() => {
    if (!chatKey) return;
    // 优先检查 Store（同步）
    if (storeChatMessages[chatKey]) return;
    // 再检查 localStorage 原始数据（避免 Store 异步恢复的竞态）
    try {
      const raw = localStorage.getItem("boss-workbench-state-v4");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.chatMessages && parsed.chatMessages[chatKey]) return;
      }
    } catch {}
    // 最后从后端加载
    loadChatMessages(chatKey).then(d => {
      if (d.active && d.active.length > 0) {
        setMessages(d.active.filter((m: {role: string; content: string}) => m.role === "user" || m.role === "assistant") as Message[]);
      }
    }).catch(() => {});
  }, [chatKey]);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [applying, setApplying] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // 每次 messages 变化 → 原子化写入 Store + 后端持久化
  useEffect(() => {
    if (!chatKey) return;
    dispatch(actions.mergeChatMessage(chatKey, messages));
    // 后端持久化：非阻塞
    saveChatMessages(chatKey, messages.length > 0 ? messages : null).catch(() => {});
  }, [messages, chatKey]);

  // 自动滚动
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  function clearChat() {
    setMessages([]);
    if (chatKey) dispatch(actions.mergeChatMessage(chatKey, null));
  }

  async function onSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    const userMsg: Message = { role: "user", content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    try {
      const { reply } = await chatWithAI({ step, context, messages: updated, profile_name: profileName });
      setMessages([...updated, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages([...updated, { role: "assistant", content: `❌ ${e instanceof Error ? e.message : "对话失败"}` }]);
    } finally { setSending(false); }
  }

  async function handleApply() {
    if (!onApply || messages.length === 0) return;
    setApplying(true);
    try { await onApply(messages); }
    finally { setApplying(false); }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="chat-header__title">💬 {title}</span>
        <div style={{ display: "flex", gap: 8 }}>
          {onApply && messages.length > 0 && (
            <button type="button" className="button-primary" onClick={handleApply} disabled={applying}
              style={{ fontSize: 11, padding: '3px 10px' }}>
              {applying ? "应用中..." : "↑ 应用到上方"}
            </button>
          )}
          {messages.length > 0 && (
            <button type="button" className="chat-header__clear" onClick={clearChat}>清空</button>
          )}
        </div>
      </div>
      <div className="chat-list" ref={listRef}>
        {messages.length === 0 && <p className="chat-empty">向 AI 提问，深入讨论这步的结果</p>}
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
        <input className="form-input form-input--inline chat-input" type="text"
          placeholder={placeholder} value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && onSend()}
          disabled={sending} />
        <button type="button" className="button-primary chat-send"
          onClick={onSend} disabled={sending || !input.trim()}>发送</button>
      </div>
    </div>
  );
};
