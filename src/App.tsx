import { useState, useRef, useCallback } from 'react'
import './App.css'

// Access Puter.js global injected by the CDN script tag
function getPuter(): any {
  const p = (window as any).puter
  if (!p) throw new Error('Puter.js is not loaded. Check your internet connection.')
  return p
}

type Stage =
  | 'upload'
  | 'analyzing'
  | 'analyzed'
  | 'suggesting'
  | 'suggested'
  | 'imagining'
  | 'done'

interface Analysis {
  classification: string
  objects: string[]
  description: string
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve((reader.result as string).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function parseJSON<T>(text: string): T {
  const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim()
  return JSON.parse(cleaned)
}

const STEP_INDEX: Record<Stage, number> = {
  upload: 0, analyzing: 1, analyzed: 1,
  suggesting: 2, suggested: 2,
  imagining: 3, done: 3,
}

export default function App() {
  const [stage, setStage] = useState<Stage>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [suggestions, setSuggestions] = useState<string[] | null>(null)
  const [generatedUrl, setGeneratedUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback((f: File) => {
    if (!f.type.startsWith('image/')) {
      setError('Please upload an image file (JPG, PNG, TIF)')
      return
    }
    setError(null)
    setFile(f)
    setImageUrl(URL.createObjectURL(f))
    setStage('upload')
  }, [])

  const runAnalyze = useCallback(async () => {
    if (!file) return
    setStage('analyzing')
    setError(null)
    try {
      const prompt =
        'Analyze this satellite image. Return ONLY valid JSON with exactly these keys:\n' +
        '{"classification":"land use type string","objects":["array","of","detected","features"],"description":"2-3 sentence aerial description"}\n' +
        'No markdown fences, no extra text, just JSON.'
      const response = await getPuter().ai.chat(prompt, file, { model: 'google/gemini-3-flash-preview' })
      const data = parseJSON<Analysis>(response.toString())
      setAnalysis(data)
      setStage('analyzed')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed. Try again.')
      setStage('upload')
    }
  }, [file])

  const runSuggest = useCallback(async () => {
    if (!analysis) return
    setStage('suggesting')
    setError(null)
    try {
      const prompt =
        `You are an urban planning expert. Given this satellite image analysis:\n` +
        `Classification: ${analysis.classification}\n` +
        `Features: ${analysis.objects.join(', ')}\n` +
        `Description: ${analysis.description}\n\n` +
        `Provide exactly 6 concise, actionable urban planning improvements.\n` +
        `Return ONLY valid JSON: {"suggestions":["...","...","...","...","...","..."]}\n` +
        `No markdown, no extra text, just JSON.`
      const response = await getPuter().ai.chat(prompt, {
        model: 'google/gemini-3-flash-preview',
      })
      const data = parseJSON<{ suggestions: string[] }>(response.toString())
      setSuggestions(data.suggestions.slice(0, 6))
      setStage('suggested')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Suggestions failed. Try again.')
      setStage('analyzed')
    }
  }, [analysis])

  const runImagine = useCallback(async () => {
    if (!file || !suggestions || !analysis) return
    setStage('imagining')
    setError(null)
    try {
      const base64 = await fileToBase64(file)
      const mimeType = (file.type === 'image/jpeg' || file.type === 'image/jpg')
        ? 'image/jpeg'
        : 'image/png'
      const prompt =
        `Transform this satellite image of "${analysis.classification}" with these urban planning improvements applied: ` +
        suggestions.slice(0, 4).join('; ') +
        '. Maintain a realistic aerial/satellite perspective. Show the transformed area clearly.'
      const imgEl = await getPuter().ai.txt2img(prompt, {
        model: 'google/gemini-3.1-flash-image-preview',
        input_image: base64,
        input_image_mime_type: mimeType,
      })
      setGeneratedUrl(imgEl.src)
      setStage('done')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Image generation failed. Try again.')
      setStage('suggested')
    }
  }, [file, suggestions, analysis])

  const reset = () => {
    setStage('upload')
    setFile(null)
    setImageUrl(null)
    setAnalysis(null)
    setSuggestions(null)
    setGeneratedUrl(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const stepNum = STEP_INDEX[stage]

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-glow" aria-hidden="true" />
        <div className="logo">
          <SatelliteIcon size={22} />
          <span>Terra<strong>Vision</strong></span>
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

      {/* ── Main Content ── */}
      <main className="content">

        {/* UPLOAD — idle, no file */}
        {stage === 'upload' && !imageUrl && (
          <div
            className={`dropzone${dragging ? ' dragging' : ''}`}
            role="button"
            tabIndex={0}
            aria-label="Upload satellite image"
            onClick={() => inputRef.current?.click()}
            onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => {
              e.preventDefault()
              setDragging(false)
              const f = e.dataTransfer.files[0]
              if (f) handleFile(f)
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
            />
            <div className="drop-icon"><SatelliteIcon size={44} /></div>
            <p className="drop-title">Drop a satellite image here</p>
            <p className="drop-sub">or <u>browse files</u> · JPG, PNG, TIF supported</p>
            <div className="drop-grid" aria-hidden="true" />
          </div>
        )}

        {/* UPLOAD — file selected, awaiting analyze */}
        {stage === 'upload' && imageUrl && (
          <div className="preview-panel">
            <div className="img-wrap">
              <img src={imageUrl} alt="Uploaded satellite" className="satellite-img" />
              <div className="grid-overlay" aria-hidden="true" />
              <div className="img-coords" aria-hidden="true">
                <span>LAT 28.61°N</span><span>LNG 77.20°E</span>
              </div>
            </div>
            <div className="preview-actions">
              <button className="btn-primary" onClick={runAnalyze}>
                <ScanIcon /> Analyze Image
              </button>
              <button className="btn-ghost" onClick={reset}>Change file</button>
            </div>
          </div>
        )}

        {/* ANALYZING */}
        {stage === 'analyzing' && imageUrl && (
          <div className="preview-panel">
            <div className="img-wrap scanning">
              <img src={imageUrl} alt="Analyzing…" className="satellite-img" />
              <div className="grid-overlay" aria-hidden="true" />
              <div className="scan-line" aria-hidden="true" />
            </div>
            <div className="status-row">
              <Spinner /> <span>Scanning satellite data with Gemini…</span>
            </div>
          </div>
        )}

        {/* ANALYSIS RESULTS (persists through remaining steps) */}
        {analysis && stage !== 'upload' && stage !== 'analyzing' && (
          <div className="results-grid">
            <div className="img-wrap">
              {imageUrl && <img src={imageUrl} alt="Original satellite" className="satellite-img" />}
              <div className="grid-overlay" aria-hidden="true" />
              <div className="img-badge">Original</div>
            </div>

            <div className="analysis-card">
              <div className="card-tag">Classification</div>
              <h2 className="classification">{analysis.classification}</h2>
              <p className="description">{analysis.description}</p>

              <div className="objects-label">Detected Features</div>
              <div className="objects-list">
                {analysis.objects.map((obj, i) => (
                  <span key={i} className="obj-chip">{obj}</span>
                ))}
              </div>

              {stage === 'analyzed' && (
                <button className="btn-primary mt" onClick={runSuggest}>
                  <LightbulbIcon /> Get Suggestions
                </button>
              )}
              {stage === 'suggesting' && (
                <div className="status-row mt">
                  <Spinner /> <span>Generating urban planning suggestions…</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SUGGESTIONS (persists through imagining and done) */}
        {suggestions && stage !== 'upload' && stage !== 'analyzing' && stage !== 'analyzed' && stage !== 'suggesting' && (
          <div className="suggestions-section">
            <div className="section-header">
              <LightbulbIcon />
              <h3>Urban Planning Suggestions</h3>
            </div>
            <div className="suggestions-grid">
              {suggestions.map((s, i) => (
                <div
                  key={i}
                  className="suggestion-card"
                  style={{ animationDelay: `${i * 40}ms` }}
                >
                  <span className="s-num">0{i + 1}</span>
                  <p>{s}</p>
                </div>
              ))}
            </div>

            {stage === 'suggested' && (
              <button className="btn-primary btn-teal" onClick={runImagine}>
                <SparkleIcon /> Imagine the Future
              </button>
            )}
            {stage === 'imagining' && (
              <div className="status-row">
                <Spinner teal /> <span>Generating future vision with Gemini…</span>
              </div>
            )}
          </div>
        )}

        {/* GENERATED IMAGE */}
        {generatedUrl && stage === 'done' && (
          <div className="compare-section">
            <div className="section-header">
              <SparkleIcon />
              <h3>Future Vision</h3>
            </div>
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
              <a className="btn-secondary" href={generatedUrl} download="terra-vision.png">
                <DownloadIcon /> Download
              </a>
              <button className="btn-primary" onClick={reset}>
                Analyze Another
              </button>
            </div>
          </div>
        )}

        {/* ERROR */}
        {error && (
          <div className="error-banner" role="alert">
            <ErrorIcon />
            <span>{error}</span>
          </div>
        )}
      </main>

      <footer className="app-footer">
        Powered by{' '}
        <a href="https://developer.puter.com" target="_blank" rel="noreferrer">
          Puter
        </a>
      </footer>
    </div>
  )
}

/* ── Icons ─────────────────────────────────────────── */

function SatelliteIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      <path d="M14 6l4 4M10 20l4-4" />
      <circle cx="19" cy="5" r="1" fill="currentColor" />
    </svg>
  )
}

function ScanIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" />
      <rect x="7" y="7" width="10" height="10" rx="1" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}

function LightbulbIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21h6M12 3a6 6 0 0 1 6 6c0 3.5-2.5 5-3 6.5H9C8.5 14 6 12.5 6 9a6 6 0 0 1 6-6z" />
    </svg>
  )
}

function SparkleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z" />
      <path d="M5 3l.75 2.75L8.5 7l-2.75.75L5 10.5l-.75-2.75L1.5 7l2.75-.75L5 3z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function Spinner({ teal = false }: { teal?: boolean }) {
  return <div className={`spinner${teal ? ' teal' : ''}`} aria-label="Loading" role="status" />
}
