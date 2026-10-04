import React from 'react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Header({ onNewEntry }: { onNewEntry: () => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)
  const resultsRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        onNewEntry()
      }
      if (e.key === 'Escape') {
        setShowResults(false)
        inputRef.current?.blur()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onNewEntry])

  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (resultsRef.current && !resultsRef.current.contains(e.target as Node) && e.target !== inputRef.current) {
        setShowResults(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSearch = async (q: string) => {
    setQuery(q)
    if (!q.trim()) { setShowResults(false); return }
    setSearching(true)
    try {
      const res = await api.search(q, 10)
      setSearchResults(res.entries)
      setShowResults(true)
    } catch { } finally { setSearching(false) }
  }

  return (
    <header className="bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center gap-4">
      <div className="flex-1 max-w-xl relative">
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">🔍</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => handleSearch(e.target.value)}
            onFocus={() => query && setShowResults(true)}
            placeholder="Search... (Ctrl+K)"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-200 outline-none focus:border-blue-500 placeholder-gray-500"
          />
        </div>
        {showResults && (
          <div ref={resultsRef} className="absolute z-50 top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl max-h-96 overflow-y-auto">
            {searching ? (
              <div className="p-4 text-center text-gray-500 text-sm">Searching...</div>
            ) : searchResults.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">Nothing found</div>
            ) : (
              searchResults.map((entry: any) => (
                <button
                  key={entry.id}
                  onClick={() => { navigate(`/entry/${entry.id}`); setShowResults(false); setQuery('') }}
                  className="w-full text-left px-4 py-3 hover:bg-gray-800 border-b border-gray-800 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    {entry.is_favorite && <span className="text-yellow-400 text-xs">⭐</span>}
                    <span className="text-gray-200 text-sm font-medium truncate">{entry.title}</span>
                  </div>
                  {entry.category_name && (
                    <span className="text-xs text-gray-500 ml-6">{entry.category_name}</span>
                  )}
                </button>
              ))
            )}
          </div>
        )}
      </div>
      <button
        onClick={onNewEntry}
        className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 whitespace-nowrap"
      >
        <span>+</span> New Entry
      </button>
    </header>
  )
}
