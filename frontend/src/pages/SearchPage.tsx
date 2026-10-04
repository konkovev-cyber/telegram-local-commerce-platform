import React, { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import type { Entry } from '../types'
import { EntryCard, EmptyState } from '../components/EntryCard'

export default function SearchPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''
  const [query, setQuery] = useState(initialQuery)
  const [entries, setEntries] = useState<Entry[]>([])
  const [total, setTotal] = useState(0)
  const [searching, setSearching] = useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const doSearch = async (q: string) => {
    if (!q.trim()) { setEntries([]); setTotal(0); return }
    setSearching(true)
    try {
      const res = await api.search(q, 50)
      setEntries(res.entries)
      setTotal(res.total)
    } catch { } finally { setSearching(false) }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setQuery(val)
    setSearchParams(val ? { q: val } : {})
    const timer = setTimeout(() => doSearch(val), 300)
    return () => clearTimeout(timer)
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="border-b border-gray-800 px-6 py-4 bg-gray-900">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-200 text-sm">← Назад</button>
          <input
            ref={inputRef}
            value={query}
            onChange={handleChange}
            placeholder="Поиск записей..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 outline-none focus:border-blue-500"
          />
          {query && (
            <button onClick={() => { setQuery(''); setSearchParams({}); setEntries([]); setTotal(0); }} className="text-gray-500 hover:text-gray-300 text-sm">✕</button>
          )}
        </div>
        {query && <p className="text-xs text-gray-500 mt-2">{searching ? 'Ищем...' : `Найдено: ${total}`}</p>}
      </div>

      <div className="p-6">
        {searching ? (
          <div className="text-gray-500 text-center py-20">Ищем...</div>
        ) : entries.length === 0 && query ? (
          <EmptyState message="Ничего не найдено" sub="Попробуйте другой запрос" />
        ) : entries.length === 0 ? (
          <div className="text-gray-600 text-center py-20 text-sm">Начните ввод для поиска</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {entries.map((entry: Entry) => (
              <div key={entry.id} onClick={() => navigate(`/entry/${entry.id}`)} className="cursor-pointer">
                <EntryCard entry={entry} onClick={() => navigate(`/entry/${entry.id}`)} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
