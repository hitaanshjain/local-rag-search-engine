import { useRef, useState } from "react";
import { Send, Bot, User, Loader2, Square } from "lucide-react";
import { citationParts, documentUrl, streamChat } from "./chatClient";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState([
    { role: "bot", text: "Hello! I've read your document. Ask me anything." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const requestController = useRef(null);

  const sendMessage = async () => {
    if (loading || !input.trim()) return;

    const userMessage = { role: "user", text: input };
    const replyId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: replyId, role: "bot", text: "", sources: [] },
    ]);
    setInput("");
    setLoading(true);
    const controller = new AbortController();
    requestController.current = controller;

    const updateReply = (update) => {
      setMessages((prev) => prev.map((msg) => (
        msg.id === replyId ? { ...msg, ...update(msg) } : msg
      )));
    };

    try {
      await streamChat(userMessage.text, (event, data) => {
        if (event === "sources") updateReply(() => ({ sources: data.sources }));
        if (event === "token") updateReply((msg) => ({ text: msg.text + data.text }));
      }, { signal: controller.signal, apiBase: API_BASE });
    } catch (error) {
      if (error.name === "AbortError") {
        updateReply((msg) => ({ text: `${msg.text}\n\nStopped.`.trim() }));
      } else {
        updateReply((msg) => ({ text: `${msg.text}\n\n${error.message}`.trim() }));
      }
    } finally {
      requestController.current = null;
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col items-center p-4">
      <div className="w-full max-w-2xl flex items-center gap-3 mb-6 mt-4">
        <div className="p-3 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/20">
          <Bot className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Local RAG Search</h1>
      </div>

      <div className="flex-1 w-full max-w-2xl bg-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col border border-gray-700">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === "user" ? "bg-purple-600" : "bg-blue-600"}`}>
                {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={`max-w-[80%] rounded-2xl px-5 py-3 ${msg.role === "user" ? "bg-purple-600 text-white rounded-br-none" : "bg-gray-700 text-gray-100 rounded-bl-none"}`}>
                <p className="leading-relaxed whitespace-pre-wrap">
                  {citationParts(msg.text, msg.sources?.length ?? 0).map((part, i) => (
                    part.number ? (
                      <a key={i} href={documentUrl(API_BASE, msg.sources[part.number - 1])} target="_blank" rel="noopener noreferrer" className="text-blue-300 underline" aria-label={`Open source ${part.number} at its PDF page`}>[{part.number}]</a>
                    ) : <span key={i}>{part.text}</span>
                  ))}
                </p>
                {msg.sources?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-600 text-xs text-gray-300">
                    <p className="font-semibold mb-1">Sources</p>
                    {msg.sources.map((src, i) => (
                      <details key={`${src.source}-${src.page}-${i}`} className="mb-1">
                        <summary><a href={documentUrl(API_BASE, src)} target="_blank" rel="noopener noreferrer" className="text-blue-300 underline" onClick={(event) => event.stopPropagation()}>[{i + 1}] {src.source}, page {src.page}</a></summary>
                        <p className="mt-1 whitespace-pre-wrap text-gray-400">{src.excerpt}</p>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex gap-4">
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                <Loader2 className="animate-spin" size={16} />
              </div>
              <div className="bg-gray-700 px-5 py-3 rounded-2xl rounded-bl-none text-gray-400 animate-pulse">
                Thinking...
              </div>
            </div>
          )}
        </div>

        <div className="p-4 bg-gray-800 border-t border-gray-700">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Ask a question about your document..."
              className="flex-1 bg-gray-900 border border-gray-600 text-white rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-500"
            />
            {loading ? (
              <button onClick={() => requestController.current?.abort()} aria-label="Stop response" className="bg-red-700 hover:bg-red-600 text-white p-3 rounded-xl transition-colors"><Square size={20} /></button>
            ) : (
              <button onClick={sendMessage} disabled={!input.trim()} aria-label="Send message" className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"><Send size={20} /></button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
