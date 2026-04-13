import { useRef } from 'react'
import './App.css'

import { usePipeline } from './hooks/usePipeline'
import { useChat } from './hooks/useChat'
import SidePanel from './components/SidePanel'
import {
  SatelliteIcon, ScanIcon, LightbulbIcon, SparkleIcon,
  CheckIcon, DownloadIcon, ErrorIcon, ChatIcon, CloseIcon, Spinner,
} from './components/Icons'
import { STEP_INDEX } from './lib/types'

export default function App() {
  const {
    stage, imageUrl, analysis, suggestions, generatedUrl, error,
    handleFile, runAnalyze, runSuggest, runImagine, reset,
  } = usePipeline()

  const {
    chatOpen, setChatOpen, messages, chatInput, setChatInput,
    chatLoading, messagesEndRef, sendMessage, resetChat,
  } = useChat(analysis, suggestions)

  const inputRef = useRef<HTMLInputElement | null>(null)
  const stepNum = STEP_INDEX[stage]
  const showChat = suggestions !== null

  const handleReset = () => { reset(); resetChat() }

  return (
    <div className="app">

      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-glow" aria-hidden="true" />
        <div className="logo">
          <SatelliteIcon size={22} />
          <span>Super<strong>Net</strong></span>
        </div>
        <p className="tagline">AI-powered satellite image intelligence</p>
      </header>

      {/* ── Step Indicator ── */}
      <nav className="stepper" aria-label="Pipeline steps">
        {(['Analyze', 'Suggest', 'Imagine'] as const).map((label, i) => (
          <div key={label} className={`step ${stepNum > i + 1 ? 'done' : stepNum === i + 1 ? 'active' : ''}`}>
            <div className="step-dot" aria-label={`Step ${i + 1}: ${label}`}>
              {stepNum > i + 1 ? <CheckIcon /> : <span>{i + 1}</span>}
            </div>
            <span className="step-label">{label}</span>
            {i < 2 && <div className={`step-line ${stepNum > i + 2 ? 'filled' : ''}`} />}
          </div>
        ))}
      </nav>

      {/* ── Body ── */}
      <div className="app-body">
        <main className="content">
          <UploadZone
            show={stage === 'upload' && !imageUrl}
            inputRef={inputRef}
            onFile={handleFile}
          />

          <PreviewPanel
            show={stage === 'upload' && !!imageUrl}
            imageUrl={imageUrl}
            onAnalyze={runAnalyze}
            onReset={handleReset}
          />

          <AnalyzingPanel show={stage === 'analyzing'} imageUrl={imageUrl} />

          <AnalysisCard
            show={!!analysis && stage !== 'upload' && stage !== 'analyzing'}
            imageUrl={imageUrl}
            analysis={analysis}
            stage={stage}
            onSuggest={runSuggest}
          />

          <SuggestionsPanel
            show={!!suggestions && !['upload','analyzing','analyzed','suggesting'].includes(stage)}
            suggestions={suggestions}
            stage={stage}
            onImagine={runImagine}
          />

          <ComparePanel
            show={!!generatedUrl && stage === 'done'}
            imageUrl={imageUrl}
            generatedUrl={generatedUrl}
            onReset={handleReset}
          />

          {error && (
            <div className="error-banner" role="alert"><ErrorIcon /><span>{error}</span></div>
          )}
        </main>

        {showChat && (
          <SidePanel
            open={chatOpen}
            messages={messages}
            chatInput={chatInput}
            chatLoading={chatLoading}
            messagesEndRef={messagesEndRef}
            onClose={() => setChatOpen(false)}
            onInputChange={setChatInput}
            onSend={sendMessage}
          />
        )}
      </div>

      <footer className="app-footer">
        © 2025 SuperNet · AI Satellite Intelligence
      </footer>

      {showChat && (
        <button
          className={`chat-fab${chatOpen ? ' active' : ''}`}
          onClick={() => setChatOpen(o => !o)}
          aria-label={chatOpen ? 'Close chat' : 'Ask AI about improvements'}
        >
          {chatOpen ? <CloseIcon /> : <ChatIcon />}
        </button>
      )}
    </div>
  )
}

/* ── Sub-components ──────────────────────────────────────────────── */

function UploadZone({ show, inputRef, onFile }: {
  show: boolean
  inputRef: React.RefObject<HTMLInputElement | null>
  onFile: (f: File) => void
}) {
  if (!show) return null
  return (
    <div
      className="dropzone"
      role="button" tabIndex={0} aria-label="Upload satellite image"
      onClick={() => inputRef.current?.click()}
      onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
      onDragOver={e => e.preventDefault()}
      onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) onFile(f) }}
    >
      <input ref={inputRef} type="file" accept="image/*" hidden
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f) }} />
      <div className="drop-icon"><SatelliteIcon size={44} /></div>
      <p className="drop-title">Drop a satellite image here</p>
      <p className="drop-sub">or <u>browse files</u> · JPG, PNG, TIF supported</p>
      <div className="drop-grid" aria-hidden="true" />
    </div>
  )
}

function PreviewPanel({ show, imageUrl, onAnalyze, onReset }: {
  show: boolean; imageUrl: string | null; onAnalyze: () => void; onReset: () => void
}) {
  if (!show || !imageUrl) return null
  return (
    <div className="preview-panel">
      <div className="img-wrap">
        <img src={imageUrl} alt="Uploaded satellite" className="satellite-img" />
        <div className="grid-overlay" aria-hidden="true" />
        <div className="img-coords" aria-hidden="true">
          <span>LAT 28.61°N</span><span>LNG 77.20°E</span>
        </div>
      </div>
      <div className="preview-actions">
        <button className="btn-primary" onClick={onAnalyze}><ScanIcon /> Analyze Image</button>
        <button className="btn-ghost" onClick={onReset}>Change file</button>
      </div>
    </div>
  )
}

function AnalyzingPanel({ show, imageUrl }: { show: boolean; imageUrl: string | null }) {
  if (!show || !imageUrl) return null
  return (
    <div className="preview-panel">
      <div className="img-wrap scanning">
        <img src={imageUrl} alt="Analyzing…" className="satellite-img" />
        <div className="grid-overlay" aria-hidden="true" />
        <div className="scan-line" aria-hidden="true" />
      </div>
      <div className="status-row"><Spinner /><span>Scanning satellite data…</span></div>
    </div>
  )
}

function AnalysisCard({ show, imageUrl, analysis, stage, onSuggest }: {
  show: boolean; imageUrl: string | null; analysis: any; stage: string; onSuggest: () => void
}) {
  if (!show || !analysis) return null
  return (
    <>
      <div className="results-grid">
        <div className="img-wrap img-wrap--fill">
          {imageUrl && <img src={imageUrl} alt="Original satellite" className="satellite-img satellite-img--fill" />}
          <div className="grid-overlay" aria-hidden="true" />
          <div className="img-badge">Original</div>
        </div>
        <div className="analysis-card">
          <div className="card-tag">Classification</div>
          <h2 className="classification">{analysis.classification}</h2>
          <p className="description">{analysis.description}</p>
          <div className="objects-label">Detected Features</div>
          <div className="objects-list">
            {analysis.objects.map((obj: string, i: number) => <span key={i} className="obj-chip">{obj}</span>)}
          </div>
          <div className="card-footer">
            {stage === 'analyzed' && (
              <button className="btn-primary" onClick={onSuggest}><LightbulbIcon /> Get Suggestions</button>
            )}
            {stage === 'suggesting' && (
              <div className="status-row"><Spinner /><span>Generating urban planning suggestions…</span></div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function SuggestionsPanel({ show, suggestions, stage, onImagine }: {
  show: boolean; suggestions: string[] | null; stage: string; onImagine: () => void
}) {
  if (!show || !suggestions) return null
  return (
    <div className="suggestions-section">
      <div className="section-header"><LightbulbIcon /><h3>Urban Planning Suggestions</h3></div>
      <div className="suggestions-grid">
        {suggestions.map((s, i) => (
          <div key={i} className="suggestion-card" style={{ animationDelay: `${i * 40}ms` }}>
            <span className="s-num">0{i + 1}</span>
            <p>{s}</p>
          </div>
        ))}
      </div>
      {stage === 'suggested' && (
        <button className="btn-primary btn-teal" onClick={onImagine}><SparkleIcon /> Imagine the Future</button>
      )}
      {stage === 'imagining' && (
        <div className="status-row"><Spinner teal /><span>Generating future vision…</span></div>
      )}
    </div>
  )
}

function ComparePanel({ show, imageUrl, generatedUrl, onReset }: {
  show: boolean; imageUrl: string | null; generatedUrl: string | null; onReset: () => void
}) {
  if (!show || !generatedUrl) return null
  return (
    <div className="compare-section">
      <div className="section-header"><SparkleIcon /><h3>Future Vision</h3></div>
      <div className="compare-grid">
        <div className="compare-panel">
          <div className="compare-label">Current State</div>
          {imageUrl && <img src={imageUrl} alt="Original" className="compare-img" />}
        </div>
        <div className="compare-arrow" aria-hidden="true">→</div>
        <div className="compare-panel">
          <div className="compare-label teal">Future Vision</div>
          <img src={generatedUrl} alt="AI-generated improved city" className="compare-img generated" />
        </div>
      </div>
      <div className="final-actions">
        <a className="btn-secondary" href={generatedUrl} download="supernet-vision.png">
          <DownloadIcon /> Download
        </a>
        <button className="btn-primary" onClick={onReset}>Analyze Another</button>
      </div>
    </div>
  )
}
