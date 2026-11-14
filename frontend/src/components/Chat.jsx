import { useEffect, useRef, useState } from "react";
import { getLatestMeasurement, sendMessage } from "../services/api.js";
import MiniReadings from "./MiniReadings.jsx";

const STORAGE_KEY = "cebollita.conversation_id";

// Botones de sugerencia. `local: true` se resuelve con los datos de los sensores, sin llamar a Gemini.
const SUGGESTIONS = [
  { label: "¿Cómo estás?", text: "¿Cómo estás hoy?" },
  { label: "¿Necesitás agua?", text: "¿Necesitás agua?" },
  { label: "📊 Mostrame tus datos", text: "Mostrame tus datos", local: true },
];

function loadConversationId() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function saveConversationId(id) {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* sin almacenamiento: la conversacion dura lo que dure la pagina */
  }
}

const formatTime = (date) =>
  date.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", hour12: false });

export default function Chat({ greeting }) {
  const [messages, setMessages] = useState(() => [
    { id: 0, role: "bot", kind: "text", time: new Date(), text: `${greeting} Qué lindo que estés por acá 🌱` },
  ]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const conversationId = useRef(loadConversationId());
  const nextId = useRef(1);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  function push(role, payload) {
    setMessages((current) => [...current, { id: nextId.current++, role, kind: "text", time: new Date(), ...payload }]);
  }

  async function submit(text, { local = false } = {}) {
    text = text.trim();
    if (!text || sending) return;
    push("user", { text });
    setSending(true);
    try {
      if (local) {
        const measurement = await getLatestMeasurement();
        if (measurement) push("bot", { kind: "data", measurement });
        else push("bot", { text: "Todavía no tengo mediciones guardadas, querido." });
      } else {
        const data = await sendMessage(text, conversationId.current);
        conversationId.current = data.conversation_id;
        saveConversationId(data.conversation_id);
        push("bot", { text: data.reply });
      }
    } catch (error) {
      push("bot", { text: error.message, error: true });
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    const text = draft;
    setDraft("");
    submit(text);
  }

  return (
    <section className="chat" aria-label="Chat con Cebollita">
      <ol className="chat__messages" aria-live="polite">
        {messages.map((m) => (
          <li
            key={m.id}
            className={`bubble bubble--${m.role}${m.error ? " bubble--error" : ""}${m.kind === "data" ? " bubble--data" : ""}`}
          >
            {m.kind === "data" ? <MiniReadings measurement={m.measurement} /> : m.text}
            <time className="bubble__time" dateTime={m.time.toISOString()}>{formatTime(m.time)}</time>
          </li>
        ))}
        {sending && (
          <li className="bubble bubble--bot bubble--typing" aria-label="Cebollita está escribiendo">
            <span /> <span /> <span />
          </li>
        )}
        <li ref={endRef} aria-hidden="true" />
      </ol>

      <div className="chat__chips" role="group" aria-label="Sugerencias">
        {SUGGESTIONS.map((s) => (
          <button key={s.label} type="button" disabled={sending} onClick={() => submit(s.text, { local: s.local })}>
            {s.label}
          </button>
        ))}
      </div>

      <form className="chat__form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Escribile a Cebollita…"
          maxLength={2000}
          aria-label="Mensaje"
        />
        <button type="submit" disabled={!draft.trim() || sending} aria-label="Enviar">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      </form>
    </section>
  );
}
