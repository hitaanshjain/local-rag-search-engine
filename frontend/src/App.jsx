import { useEffect, useRef, useState } from "react";
import { Send, Bot, User, Loader2, Square, RotateCcw } from "lucide-react";
import { citationParts, documentUrl, streamChat } from "./chatClient";
import { DOCUMENT_KEY, MESSAGE_KEY, historyForRequest, readStoredJson, selectedAvailableDocuments } from "./conversation";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState(() => {
    const stored = readStoredJson(localStorage, MESSAGE_KEY, []);
    return Array.isArray(stored) ? stored : [];
  });
  const [documents, setDocuments] = useState([]);
  const [selectedDocuments, setSelectedDocuments] = useState(null);
  const [documentError, setDocumentError] = useState("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const requestController = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/documents`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Could not load indexed documents.");
        return response.json();
      })
      .then((data) => {
        const catalog = data.documents || [];
        setDocuments(catalog);
        setSelectedDocuments(selectedAvailableDocuments(readStoredJson(localStorage, DOCUMENT_KEY, null), catalog));
      })
      .catch((error) => {
        if (error.name !== "AbortError") setDocumentError(error.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => { localStorage.setItem(MESSAGE_KEY, JSON.stringify(messages)); }, [messages]);
  useEffect(() => {
    if (selectedDocuments !== null) localStorage.setItem(DOCUMENT_KEY, JSON.stringify(selectedDocuments));
  }, [selectedDocuments]);

  const newConversation = () => {
    requestController.current?.abort();
    requestController.current = null;
    setMessages([]);
    setInput("");
    setStatus("");
    setLoading(false);
  };

  const toggleDocument = (name) => {
    setSelectedDocuments((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
  };

  const sendMessage = async () => {
    if (loading || !input.trim() || !selectedDocuments?.length) return;

    const history = historyForRequest(messages);
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
        if (requestController.current !== controller) return;
        if (event === "status") setStatus(data.text);
        if (event === "sources") updateReply(() => ({ sources: data.sources }));
        if (event === "token") updateReply((msg) => ({ text: msg.text + data.text }));
      }, { signal: controller.signal, apiBase: API_BASE, history, documents: selectedDocuments });
    } catch (error) {
      if (requestController.current !== controller) return;
      if (error.name === "AbortError") {
        updateReply((msg) => ({ text: `${msg.text}\n\nStopped.`.trim() }));
      } else {
        updateReply((msg) => ({ text: `${msg.text}\n\n${error.message}`.trim() }));
      }
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setStatus("");
        setLoading(false);
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col items-center p-4">
      <div className="w-full max-w-2xl flex items-center gap-3 mb-6 mt-4">
        <div className="p-3 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/20">
          <Bot className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Local RAG Search</h1>
        <button onClick={newConversation} className="ml-auto flex items-center gap-2 rounded-lg border border-gray-600 px-3 py-2 text-sm hover:bg-gray-800" aria-label="New conversation"><RotateCcw size={16} /> New conversation</button>
      </div>

      <div className="flex-1 w-full max-w-2xl bg-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col border border-gray-700">
        <fieldset className="border-b border-gray-700 p-4">
          <legend className="sr-only">Documents to search</legend>
          <p className="mb-2 text-sm font-semibold">Documents to search</p>
          {documentError && <p role="alert" className="text-sm text-red-300">{documentError}</p>}
          {!documentError && documents.length === 0 && <p className="text-sm text-gray-400">No indexed documents available.</p>}
          <div className="flex flex-wrap gap-3">
            {documents.map((doc) => <label key={doc.name} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={selectedDocuments?.includes(doc.name) ?? false} onChange={() => toggleDocument(doc.name)} />
              <span>{doc.name}</span>
              {doc.low_text_pages?.length > 0 && <span className="text-amber-300" title={`Low text on pages ${doc.low_text_pages.join(", ")}`}>⚠ {doc.low_text_pages.length} low text {doc.low_text_pages.length === 1 ? "page" : "pages"}</span>}
            </label>)}
          </div>
          {selectedDocuments?.length === 0 && documents.length > 0 && <p className="mt-2 text-sm text-amber-300">Select at least one document to ask a question.</p>}
        </fieldset>
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && <p className="text-gray-400">Ask a question about the selected documents.</p>}
          {messages.filter((msg) => msg.text || msg.sources?.length).map((msg, idx) => (
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
                        <summary><a href={documentUrl(API_BASE, src)} target="_blank" rel="noopener noreferrer" className="text-blue-300 underline" onClick={(event) => event.stopPropagation()}>[{i + 1}] {src.source}, page {src.page}</a>{src.low_text && <span className="ml-2 text-amber-300">Low text extracted</span>}</summary>
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
              <div role="status" aria-live="polite" className="bg-gray-700 px-5 py-3 rounded-2xl rounded-bl-none text-gray-400 animate-pulse">
                {status || "Thinking..."}
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
              placeholder="Ask a question about the selected documents..."
              className="flex-1 bg-gray-900 border border-gray-600 text-white rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-500"
            />
            {loading ? (
              <button onClick={() => requestController.current?.abort()} aria-label="Stop response" className="bg-red-700 hover:bg-red-600 text-white p-3 rounded-xl transition-colors"><Square size={20} /></button>
            ) : (
              <button onClick={sendMessage} disabled={!input.trim() || !selectedDocuments?.length} aria-label="Send message" className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"><Send size={20} /></button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
