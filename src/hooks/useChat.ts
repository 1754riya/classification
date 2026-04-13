import { useState, useRef, useCallback, useEffect } from 'react'
import { getPuter } from '../lib/puter'
import type { Analysis, Message } from '../lib/types'

export function useChat(analysis: Analysis | null, suggestions: string[] | null) {
  const [chatOpen, setChatOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, chatLoading])

  const sendMessage = useCallback(async (text?: string) => {
    const input = (text ?? chatInput).trim()
    if (!input || chatLoading || !analysis || !suggestions) return
    setChatInput('')
    const userMsg: Message = { role: 'user', text: input }
    const next = [...messages, userMsg]
    setMessages(next)
    setChatLoading(true)
    try {
      const system =
        `You are a concise urban planning assistant for SuperNet AI. ` +
        `The satellite image shows a "${analysis.classification}". ` +
        `Detected features: ${analysis.objects.join(', ')}. ${analysis.description} ` +
        `Suggested improvements:\n${suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n')}` +
        `\nAnswer in 2–4 sentences. Be specific and practical.`
      const history = next.map(m => ({ role: m.role, content: m.text }))
      const response = await getPuter().ai.chat(
        [{ role: 'system', content: system }, ...history],
        { model: 'google/gemini-3-flash-preview' }
      )
      setMessages(p => [...p, { role: 'assistant', text: response.toString() }])
    } catch {
      setMessages(p => [...p, { role: 'assistant', text: 'Something went wrong. Please try again.' }])
    }
    setChatLoading(false)
  }, [chatInput, chatLoading, messages, analysis, suggestions])

  const resetChat = useCallback(() => {
    setChatOpen(false)
    setMessages([])
    setChatInput('')
  }, [])

  return { chatOpen, setChatOpen, messages, chatInput, setChatInput, chatLoading, messagesEndRef, sendMessage, resetChat }
}
