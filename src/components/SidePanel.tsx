import { CloseIcon, SendIcon } from './Icons'
import type { Message } from '../lib/types'

const STARTERS = [
  'Biggest environmental impact?',
  'Estimated cost?',
  'Which to prioritize first?',
  'Implementation timeline?',
]

function BotAvatar() {
  return (
    <div className="bot-avatar" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="10" rx="2" />
        <path d="M12 11V7M8 7h8M12 3v4" />
        <circle cx="8.5" cy="16" r="1" fill="currentColor" />
        <circle cx="15.5" cy="16" r="1" fill="currentColor" />
      </svg>
    </div>
  )
}

function MsgAvatar() {
  return (
    <div className="msg-avatar" aria-hidden="true">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="10" rx="2" />
        <path d="M12 11V7M8 7h8" />
        <circle cx="8.5" cy="16" r="1" fill="currentColor" />
        <circle cx="15.5" cy="16" r="1" fill="currentColor" />
      </svg>
    </div>
  )
}

interface Props {
  open: boolean
  messages: Message[]
  chatInput: string
  chatLoading: boolean
  messagesEndRef: React.RefObject<HTMLDivElement | null>
  onClose: () => void
  onInputChange: (v: string) => void
  onSend: (text?: string) => void
}

export default function SidePanel({
  open, messages, chatInput, chatLoading, messagesEndRef, onClose, onInputChange, onSend,
}: Props) {
  return (
    <aside className={`side-panel${open ? ' open' : ''}`} aria-label="Ask AI about suggestions">

      {/* Gradient header */}
      <div className="panel-header">
        <div className="panel-header-row">
          <div className="panel-bot-info">
            <BotAvatar />
            <div>
              <div className="panel-bot-name">SuperNet AI</div>
              <div className="panel-bot-status">
                <span className="status-dot" aria-hidden="true" />
                <span>Online</span>
              </div>
            </div>
          </div>
          <button className="panel-close" onClick={onClose} aria-label="Close chat">
            <CloseIcon />
          </button>
        </div>
        {messages.length === 0 && (
          <p className="panel-welcome">
            Ask me anything about the suggested improvements
          </p>
        )}
      </div>

      {/* Messages / starters */}
      <div className="panel-messages">
        {messages.length === 0 ? (
          <div className="starters">
            {STARTERS.map((s, i) => (
              <button key={i} className="starter-chip" onClick={() => onSend(s)}>
                {s}
              </button>
            ))}
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`msg msg-${m.role}`}>
              {m.role === 'assistant' && <MsgAvatar />}
              <p>{m.text}</p>
            </div>
          ))
        )}

        {chatLoading && (
          <div className="msg msg-assistant">
            <MsgAvatar />
            <div className="typing-dots">
              <span /><span /><span />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="panel-input">
        <input
          value={chatInput}
          onChange={e => onInputChange(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() }
          }}
          placeholder="Ask about the improvements…"
          aria-label="Chat message"
          disabled={chatLoading}
        />
        <button
          className="send-btn"
          onClick={() => onSend()}
          disabled={chatLoading || !chatInput.trim()}
          aria-label="Send"
        >
          <SendIcon />
        </button>
      </div>
    </aside>
  )
}
