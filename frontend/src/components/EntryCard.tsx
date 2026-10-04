import React from 'react'

interface Props {
  entry: { id: number; title: string; content: string; category_name: string | null; is_favorite: boolean; tags: { id: number; name: string }[]; updated_at: string }
  onClick: () => void
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Только что'
  if (mins < 60) return `${mins} мин.`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}ч`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}д`
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

function extractKeyData(content: string): string {
  // Extract first login|password pair or first IP
  const credMatch = content.match(/[-*]\s*`?([a-zA-Z0-9_.@-]+)`?\s*\|\s*`?([^`|]+)`?/)
  if (credMatch) return `${credMatch[1]} • ${credMatch[2].slice(0, 6)}...`
  const ipMatch = content.match(/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/)
  if (ipMatch) return ipMatch[0]
  const urlMatch = content.match(/https?:\/\/[^\s|]+/)
  if (urlMatch) return urlMatch[0].slice(0, 30)
  const lines = content.split('\n').filter(l => l.trim() && !l.startsWith('#') && !l.startsWith('---'))
  return lines[0]?.slice(0, 120) || ''
}

export function EntryCard({ entry, onClick }: Props) {
  const preview = extractKeyData(entry.content)

  return (
    <div
      className="entry-card border border-gray-800 rounded-lg p-3.5 cursor-pointer group"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <h3 className="font-semibold text-gray-100 text-sm truncate flex-1">{entry.title}</h3>
        <div className="flex items-center gap-1 flex-shrink-0">
          {entry.is_favorite && <span className="text-yellow-400 text-xs">⭐</span>}
          <span className="card-actions opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-gray-600 text-xs">📋</span>
          </span>
        </div>
      </div>
      {entry.category_name && (
        <span className="inline-block text-xs text-gray-500 mb-1.5 bg-gray-800 px-2 py-0.5 rounded">{entry.category_name}</span>
      )}
      {preview && (
        <p className="text-gray-500 text-xs mt-1 line-clamp-2 font-mono bg-gray-900/50 rounded px-2 py-1">
          {preview}
        </p>
      )}
      <div className="flex items-center justify-between mt-2">
        <div className="flex flex-wrap gap-1">
          {entry.tags.slice(0, 3).map(tag => (
            <span key={tag.id} className="tag-badge">#{tag.name}</span>
          ))}
        </div>
        <span className="text-xs text-gray-700 flex-shrink-0 ml-2">{formatDate(entry.updated_at)}</span>
      </div>
    </div>
  )
}

export function EmptyState({ message, sub, action }: { message: string; sub?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-4xl mb-4 opacity-30">📦</div>
      <p className="text-gray-400 text-lg mb-1">{message}</p>
      {sub && <p className="text-gray-600 text-sm mb-6">{sub}</p>}
      {action}
    </div>
  )
}
