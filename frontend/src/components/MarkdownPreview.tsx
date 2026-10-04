import React from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface Props {
  content: string
}

const IP_RE = /\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d{1,5})?)\b/g
const URL_RE = /(https?:\/\/[^\s<>"')\]]+)/g
const EMAIL_RE = /\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b/g
const PASSWORD_LABEL_RE = /(?:пароль|password|pwd|pass)\s*[:：]\s*/gi
const CREDENTIAL_RE = /\|\s*([^\|]+?)\s*\|\s*(`[^`]+`|[^\|]+?)\s*\|/g

function isPasswordLike(text: string): boolean {
  return /[!@#$%^&*()_+\-=\[\]{};':",.<>?/\\|`~]/.test(text) && text.length >= 4
}

function CopyButton({ text, label = 'Копировать' }: { text: string; label?: string }) {
  const [copied, setCopied] = React.useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      onClick={copy}
      title={`Копировать: ${text}`}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-mono transition-all ${
        copied
          ? 'bg-green-500/20 text-green-400'
          : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
      }`}
    >
      {copied ? '✓ Скопировано' : `📋 ${label}`}
    </button>
  )
}

function SmartText({ children }: { children: React.ReactNode }) {
  const text = String(children)
  if (!text) return <>{children}</>

  const parts: React.ReactNode[] = []
  let lastIndex = 0
  const regex = new RegExp(
    `(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}(?::\\d{1,5})?)` +
    `|(https?:\\/\\/[^\s<>"')\\]\\]]+)` +
    `|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})` +
    `|(\|[^\|]*?\|(?:\s*\||$))`,
    'g'
  )

  let match
  let processed = text
  let offset = 0

  // Simpler approach: process the text and wrap matches
  const segments: { text: string; type?: 'ip' | 'url' | 'email' | 'credential' }[] = []
  let pos = 0
  const s = text

  while (pos < s.length) {
    const ipMatch = s.slice(pos).match(IP_RE)
    const urlMatch = s.slice(pos).match(URL_RE)
    const emailMatch = s.slice(pos).match(EMAIL_RE)

    const candidates: { idx: number; len: number; type: 'ip' | 'url' | 'email' }[] = []
    if (ipMatch) candidates.push({ idx: pos + ipMatch.index!, len: ipMatch[0].length, type: 'ip' })
    if (urlMatch) candidates.push({ idx: pos + urlMatch.index!, len: urlMatch[0].length, type: 'url' })
    if (emailMatch) candidates.push({ idx: pos + emailMatch.index!, len: emailMatch[0].length, type: 'email' })

    if (candidates.length === 0) {
      segments.push({ text: s.slice(pos) })
      break
    }

    candidates.sort((a, b) => a.idx - b.idx)
    const best = candidates[0]

    if (best.idx > pos) {
      segments.push({ text: s.slice(pos, best.idx) })
    }
    segments.push({ text: s.slice(best.idx, best.idx + best.len), type: best.type })
    pos = best.idx + best.len
  }

  return (
    <span>
      {segments.map((seg, i) => {
        if (!seg.type) return <span key={i}>{seg.text}</span>
        if (seg.type === 'ip') {
          return (
            <span key={i} className="inline-flex items-center gap-1">
              <span className="text-blue-400 font-mono bg-blue-400/10 px-1 py-0.5 rounded">{seg.text}</span>
              <CopyButton text={seg.text} label="" />
            </span>
          )
        }
        if (seg.type === 'url') {
          return (
            <span key={i} className="inline-flex items-center gap-1">
              <a href={seg.text} target="_blank" rel="noreferrer" className="text-purple-400 hover:text-purple-300 underline">
                {seg.text}
              </a>
              <CopyButton text={seg.text} label="" />
            </span>
          )
        }
        if (seg.type === 'email') {
          return (
            <span key={i} className="inline-flex items-center gap-1">
              <span className="text-yellow-300 font-mono">{seg.text}</span>
              <CopyButton text={seg.text} label="" />
            </span>
          )
        }
        return <span key={i}>{seg.text}</span>
      })}
    </span>
  )
}

function PwdRow({ children }: { children: React.ReactNode }) {
  const text = String(children)
  // Match: label | `password` or label | password
  const match = text.match(/\|\s*([^|]+?)\s*\|\s*(`([^`]+)`|([^|]+?))\s*\|/)
  if (!match) return <SmartText>{children}</SmartText>

  const label = match[1].trim()
  const password = (match[3] || match[4] || '').trim()
  const isCode = !!match[3]

  if (!password || password === '—' || password === '—') {
    return <SmartText>{children}</SmartText>
  }

  return (
    <span className="inline-flex items-center gap-1 flex-wrap">
      <span className="text-gray-300">{label}</span>
      <span
        className={`font-mono px-1.5 py-0.5 rounded ${
          isPasswordLike(password)
            ? 'bg-red-500/15 text-red-300 border border-red-500/30'
            : 'bg-gray-700 text-gray-200'
        }`}
      >
        {password}
      </span>
      <CopyButton text={password} label="" />
      {isCode && (
        <span className="text-xs text-gray-500 ml-1">нажмите для копирования</span>
      )}
    </span>
  )
}

function ListItemContent({ children }: { children: React.ReactNode }) {
  const text = String(children)
  // Check if this is a credential line: starts with login | password pattern
  const credMatch = text.match(/^[-*]\s*`?([a-zA-Z0-9_.@-]+)`?\s*\|\s*`?([a-zA-Z0-9_@./$%^*&!-]+)`?/)
  if (credMatch) {
    const login = credMatch[1]
    const password = credMatch[2]
    return (
      <span className="inline-flex items-center gap-2 flex-wrap">
        <span className="text-gray-400">•</span>
        <code className="text-blue-300 bg-blue-400/10 px-1 py-0.5 rounded font-mono text-sm">{login}</code>
        <span className="text-gray-500">|</span>
        <code className="text-red-300 bg-red-500/15 px-1 py-0.5 rounded font-mono text-sm border border-red-500/30">{password}</code>
        <CopyButton text={`${login}:${password}`} label="Коп." />
        <CopyButton text={password} label="Пароль" />
      </span>
    )
  }
  return <SmartText>{children}</SmartText>
}

const components: any = {
  code({ children, className, node, ...rest }: any) {
    const match = /language-(\w+)/.exec(className || '')
    const isBlock = className?.includes('language') || (!match && String(children).includes('\n'))
    const codeStr = String(children).replace(/\n$/, '')

    if (!isBlock && !match) {
      return <code {...rest} className={className}>{children}</code>
    }

    return (
      <div className="code-block-wrapper relative my-2">
        <button
          className="code-copy-btn"
          onClick={() => navigator.clipboard.writeText(codeStr)}
        >
          📋 Копировать
        </button>
        <SyntaxHighlighter
          {...rest}
          language={match?.[1] || 'bash'}
          style={oneDark}
          PreTag="div"
          customStyle={{ margin: 0, borderRadius: '8px', paddingRight: '60px' }}
        >
          {codeStr}
        </SyntaxHighlighter>
      </div>
    )
  },
  pre({ children }: any) {
    return <>{children}</>
  },
  p({ children }: any) {
    return <p className="my-1.5">{<SmartText>{children}</SmartText>}</p>
  },
  li({ children }: any) {
    return <li className="my-0.5 py-0.5"><ListItemContent>{children}</ListItemContent></li>
  },
}

export default function MarkdownPreview({ content }: Props) {
  return (
    <div className="markdown-preview max-w-none text-sm leading-relaxed">
      <ReactMarkdown components={components}>{content}</ReactMarkdown>
    </div>
  )
}
