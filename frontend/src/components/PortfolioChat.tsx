import { useEffect, useRef, useState } from "react";
import { sendPortfolioChat, type ChatProvider } from "../api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  accountId: string;
  disabled?: boolean;
}

const PROVIDER_LABELS: Record<ChatProvider, string> = {
  gemini: "Gemini",
  groq: "Groq",
};

const STARTER_PROMPTS = [
  "Кратко опиши структуру портфеля",
  "Какие облигации ближе всего к погашению?",
  "Где самая большая доля в портфеле?",
];

export function PortfolioChat({ accountId, disabled = false }: Props) {
  const [provider, setProvider] = useState<ChatProvider>("gemini");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMessages([]);
    setError(null);
  }, [accountId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function submitMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading || disabled || !accountId) return;

    const nextMessages: ChatMessage[] = [
      ...messages,
      { role: "user", content: trimmed },
    ];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setError(null);
    setNotice(null);

    try {
      const response = await sendPortfolioChat({
        account_id: accountId,
        provider,
        messages: nextMessages,
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.reply },
      ]);
      if (response.provider !== provider) {
        setNotice(
          `Gemini недоступен — ответ получен через ${PROVIDER_LABELS[response.provider]}`,
        );
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось получить ответ",
      );
      setMessages(nextMessages.slice(0, -1));
      setInput(trimmed);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void submitMessage(input);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage(input);
    }
  }

  return (
    <section className="card portfolio-chat">
      <div className="portfolio-chat-header">
        <div>
          <h2>AI-ассистент</h2>
          <p className="portfolio-chat-hint">
            Ответы с учётом актуальных данных портфеля
          </p>
        </div>
        <select
          className="portfolio-chat-provider"
          value={provider}
          onChange={(event) => setProvider(event.target.value as ChatProvider)}
          disabled={loading}
          aria-label="Провайдер AI"
        >
          {(Object.keys(PROVIDER_LABELS) as ChatProvider[]).map((key) => (
            <option key={key} value={key}>
              {PROVIDER_LABELS[key]}
            </option>
          ))}
        </select>
      </div>

      <div className="portfolio-chat-messages">
        {messages.length === 0 && !loading && (
          <div className="portfolio-chat-empty">
            <p>Задайте вопрос о портфеле или выберите подсказку:</p>
            <div className="portfolio-chat-starters">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="portfolio-chat-starter"
                  onClick={() => void submitMessage(prompt)}
                  disabled={disabled}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

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

        {loading && (
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
          placeholder={
            disabled
              ? "Сначала загрузите портфель…"
              : "Спросите о портфеле… (Enter — отправить)"
          }
          rows={3}
          disabled={disabled || loading}
        />
        <div className="portfolio-chat-actions">
          <button
            type="button"
            className="portfolio-chat-clear"
            onClick={() => {
              setMessages([]);
              setError(null);
              setNotice(null);
            }}
            disabled={loading || messages.length === 0}
          >
            Очистить
          </button>
          <button
            type="submit"
            className="portfolio-chat-send"
            disabled={disabled || loading || !input.trim()}
          >
            Отправить
          </button>
        </div>
      </form>
    </section>
  );
}
