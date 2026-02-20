import { useState } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";

export default function App() {
  const [messages, setMessages] = useState([
    { role: "bot", text: "Hello! I've read your document. Ask me anything." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", text: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMessage.text }),
      });

      // Placeholder for streaming text
      setMessages((prev) => [...prev, { role: "bot", text: "", sources: [] }]);
      setLoading(false);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let completeResponse = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        completeResponse += decoder.decode(value, { stream: true });

        setMessages((prev) => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].text = completeResponse;
          return newMessages;
        });
      }
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [...prev, { role: "bot", text: "Error connecting to server." }]);
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
                <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>
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
            <button onClick={sendMessage} disabled={loading} className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              <Send size={20} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}