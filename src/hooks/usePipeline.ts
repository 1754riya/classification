import { useState, useCallback } from 'react'
import { getPuter, fileToBase64, parseJSON } from '../lib/puter'
import type { Stage, Analysis } from '../lib/types'

export function usePipeline() {
  const [stage, setStage] = useState<Stage>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [suggestions, setSuggestions] = useState<string[] | null>(null)
  const [generatedUrl, setGeneratedUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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
      setAnalysis(parseJSON<Analysis>(response.toString()))
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
      const response = await getPuter().ai.chat(prompt, { model: 'google/gemini-3-flash-preview' })
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
      const mimeType = (file.type === 'image/jpeg' || file.type === 'image/jpg') ? 'image/jpeg' : 'image/png'
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

  const reset = useCallback(() => {
    setStage('upload')
    setFile(null)
    setImageUrl(null)
    setAnalysis(null)
    setSuggestions(null)
    setGeneratedUrl(null)
    setError(null)
  }, [])

  return { stage, file, imageUrl, analysis, suggestions, generatedUrl, error, handleFile, runAnalyze, runSuggest, runImagine, reset }
}
