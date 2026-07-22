import { useEffect, useRef, useState } from "react";
import {
  sendBondChat,
  type BondScreenerItem,
  type ChatProvider,
} from "../api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  bond: BondScreenerItem;
  onClose: () => void;
}

const PROVIDER_LABELS: Record<ChatProvider, string> = {
  gemini: "Gemini",
  groq: "Groq",
};

const INITIAL_PROMPT =
  "Сделай summary по отчётам АКРА и Эксперт РА для эмитента этой облигации.";

const inflightInitialSummary = new Map<
  string,
  ReturnType<typeof sendBondChat>
>();

function fetchInitialSummary(bond: BondScreenerItem, provider: ChatProvider) {
  const key = `${bond.figi}:${provider}`;
  const existing = inflightInitialSummary.get(key);
  if (existing) {
    return existing;
  }

  const userMessage = { role: "user" as const, content: INITIAL_PROMPT };
  const promise = sendBondChat({
    bond,
    provider,
    messages: [userMessage],
  }).finally(() => {
    inflightInitialSummary.delete(key);
  });
  inflightInitialSummary.set(key, promise);
  return promise;
}

export function BondAiPanel({ bond, onClose }: Props) {
  const [provider, setProvider] = useState<ChatProvider>("gemini");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [apiMessages, setApiMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMessages([]);
    setApiMessages([]);
    setInput("");
    setError(null);
    setNotice(null);

    let cancelled = false;
    const userMessage: ChatMessage = { role: "user", content: INITIAL_PROMPT };

    async function loadInitialSummary() {
      setLoading(true);
      setError(null);
      setNotice(null);

      try {
        const response = await fetchInitialSummary(bond, provider);
        if (cancelled) return;

        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: response.reply,
        };
        setApiMessages([userMessage, assistantMessage]);
        setMessages([assistantMessage]);
        if (response.provider !== provider) {
          setNotice(
            `Gemini недоступен — ответ получен через ${PROVIDER_LABELS[response.provider]}`,
          );
        }
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Не удалось получить ответ",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
          textareaRef.current?.focus();
        }
      }
    }

    void loadInitialSummary();

    return () => {
      cancelled = true;
    };
    // Reload initial summary only when the instrument changes, not on every bond field update.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: bond.figi + current provider
  }, [bond.figi]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function runAnalysis(
    text: string,
    options?: { showUserMessage?: boolean; resetDisplay?: boolean },
  ) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    const nextApiMessages = options?.resetDisplay
      ? [userMessage]
      : [...apiMessages, userMessage];

    if (options?.resetDisplay) {
      setMessages([]);
    }
    if (options?.showUserMessage) {
      setMessages((prev) => [...prev, userMessage]);
    }

    setInput("");
    setLoading(true);
    setError(null);
    setNotice(null);

    try {
      const response = await sendBondChat({
        bond,
        provider,
        messages: nextApiMessages,
      });
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.reply,
      };
      setApiMessages([...nextApiMessages, assistantMessage]);
      setMessages((prev) => [...prev, assistantMessage]);
      if (response.provider !== provider) {
        setNotice(
          `Gemini недоступен — ответ получен через ${PROVIDER_LABELS[response.provider]}`,
        );
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось получить ответ",
      );
      if (options?.showUserMessage) {
        setMessages((prev) => prev.slice(0, -1));
      }
      setInput(trimmed);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void runAnalysis(input, { showUserMessage: true });
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void runAnalysis(input, { showUserMessage: true });
    }
  }

  return (
    <div className="bond-ai-overlay" onClick={onClose}>
      <aside
        className="card bond-ai-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="bond-ai-header">
          <div className="bond-ai-title">
            <h2>Summary: АКРА / Эксперт РА</h2>
            <div className="bond-ai-subtitle">
              <span className="ticker">{bond.ticker}</span>
              <span className="instrument-name">{bond.name}</span>
            </div>
          </div>
          <div className="bond-ai-header-actions">
            <select
              className="portfolio-chat-provider"
              value={provider}
              onChange={(event) =>
                setProvider(event.target.value as ChatProvider)
              }
              disabled={loading}
              aria-label="Провайдер AI"
            >
              {(Object.keys(PROVIDER_LABELS) as ChatProvider[]).map((key) => (
                <option key={key} value={key}>
                  {PROVIDER_LABELS[key]}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="bond-ai-close"
              onClick={onClose}
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>
        </div>

        <div className="portfolio-chat-messages bond-ai-messages">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`portfolio-chat-message portfolio-chat-message-${message.role}`}
            >
              <div className="portfolio-chat-message-label">
                {message.role === "user" ? "Вы" : PROVIDER_LABELS[provider]}
              </div>
              <div className="portfolio-chat-message-text">{message.content}</div>
            </div>
          ))}

          {loading && messages.length === 0 && (
            <div className="portfolio-chat-message portfolio-chat-message-assistant">
              <div className="portfolio-chat-message-label">
                {PROVIDER_LABELS[provider]}
              </div>
              <div className="portfolio-chat-message-text portfolio-chat-typing">
                Загружаю отчёты АКРА и Эксперт РА…
              </div>
            </div>
          )}

          {loading && messages.length > 0 && (
            <div className="portfolio-chat-message portfolio-chat-message-assistant">
              <div className="portfolio-chat-message-label">
                {PROVIDER_LABELS[provider]}
              </div>
              <div className="portfolio-chat-message-text portfolio-chat-typing">
                Думаю…
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {notice && <div className="portfolio-chat-notice">{notice}</div>}
        {error && <div className="portfolio-chat-error">{error}</div>}

        <form className="portfolio-chat-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className="portfolio-chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Уточняющий вопрос по отчётам эмитента…"
            rows={3}
            disabled={loading}
          />
          <div className="portfolio-chat-actions">
            <button
              type="button"
              className="portfolio-chat-clear"
              onClick={() =>
                void runAnalysis(INITIAL_PROMPT, { resetDisplay: true })
              }
              disabled={loading}
            >
              Повторить summary
            </button>
            <button
              type="submit"
              className="portfolio-chat-send"
              disabled={loading || !input.trim()}
            >
              Отправить
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}
