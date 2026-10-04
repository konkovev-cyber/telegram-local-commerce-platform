import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import type { Entry } from '../types'

function fmt(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'только что'
  if (mins < 60) return `${mins} мин.`
  const h = Math.floor(mins / 60)
  if (h < 24) return `${h} ч.`
  const days = Math.floor(h / 24)
  if (days < 7) return `${days} дн.`
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { categoryId } = useParams<{ categoryId?: string }>()
  const [entries, setEntries] = useState<Entry[]>([])
  const [filter, setFilter] = useState<'all' | 'favorite'>('all')
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')

  useEffect(() => {
    setLoading(true)
    const params: Record<string, any> = { limit: 200 }
    if (categoryId) params.category_id = Number(categoryId)
    if (filter === 'favorite') params.favorite = true

    api.getEntries(params)
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [categoryId, filter])

  const title = categoryId ? `Категория #${categoryId}` : filter === 'favorite' ? 'Избранное' : 'Все записи'
  const filtered = q
    ? entries.filter(e => e.title.toLowerCase().includes(q.toLowerCase()) ||
        e.tags.some(t => t.name.toLowerCase().includes(q.toLowerCase())))
    : entries

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="border-b border-gray-800 px-6 py-3 bg-gray-900 sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
          <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
            <button onClick={() => setFilter('all')}
              className={`px-3 py-1 rounded text-sm ${filter === 'all' ? 'bg-gray-700 text-gray-100' : 'text-gray-400 hover:text-gray-200'}`}>
              Все
            </button>
            <button onClick={() => setFilter('favorite')}
              className={`px-3 py-1 rounded text-sm ${filter === 'favorite' ? 'bg-gray-700 text-gray-100' : 'text-gray-400 hover:text-gray-200'}`}>
              ⭐ Избранное
            </button>
          </div>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Фильтр по названию/тегу..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 w-64" />
          <span className="text-xs text-gray-500">{filtered.length} шт.</span>
          <div className="flex-1" />
          <button onClick={() => navigate('/new')}
            className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap">
            + Новая запись
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-gray-500 text-center py-20">Загрузка...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-4 opacity-30">📦</div>
          <p className="text-gray-400 text-lg">Записей нет</p>
        </div>
      ) : (
        <div className="p-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
                <th className="py-2 px-2">Название</th>
                <th className="py-2 px-2 w-32">Категория</th>
                <th className="py-2 px-2">Теги</th>
                <th className="py-2 px-2 w-24 text-right">Обновлено</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(entry => (
                <tr key={entry.id} onClick={() => navigate(`/entry/${entry.id}`)}
                  className="border-b border-gray-800/50 hover:bg-gray-900/60 cursor-pointer">
                  <td className="py-2.5 px-2">
                    <div className="flex items-center gap-2">
                      {entry.is_favorite && <span className="text-yellow-400 text-xs">⭐</span>}
                      <span className="text-gray-100">{entry.title}</span>
                    </div>
                    {entry.content && (
                      <div className="text-xs text-gray-600 truncate max-w-md mt-0.5">
                        {entry.content.replace(/[#*`|>-]/g, '').slice(0, 90)}
                      </div>
                    )}
                  </td>
                  <td className="py-2.5 px-2">
                    {entry.category_name ? (
                      <span className="text-xs bg-gray-800 px-2 py-0.5 rounded text-gray-400">{entry.category_name}</span>
                    ) : <span className="text-gray-700">—</span>}
                  </td>
                  <td className="py-2.5 px-2">
                    <div className="flex flex-wrap gap-1">
                      {entry.tags.map(t => <span key={t.id} className="tag-badge">#{t.name}</span>)}
                    </div>
                  </td>
                  <td className="py-2.5 px-2 text-right text-xs text-gray-500 whitespace-nowrap">{fmt(entry.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
