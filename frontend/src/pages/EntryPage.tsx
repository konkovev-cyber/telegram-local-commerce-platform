import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import MarkdownPreview from '../components/MarkdownPreview'
import type { HistoryEntry } from '../types'
import { useApp } from '../contexts/AppContext'

function Toast({ message }: { message: string }) {
  return <div className="toast">{message}</div>
}

export default function EntryPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const { refreshAll } = useApp()
  const [entry, setEntry] = useState<any>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.getEntry(Number(id))
      .then(setEntry)
      .catch(() => navigate('/'))
      .finally(() => setLoading(false))
  }, [id])

  const showToast = useCallback((msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }, [])

  const handleCopyContent = async () => {
    if (!entry) return
    await navigator.clipboard.writeText(entry.content)
    showToast('Содержимое скопировано')
  }

  const handleCopyTitle = async () => {
    if (!entry) return
    await navigator.clipboard.writeText(entry.title)
    showToast('Название скопировано')
  }

  const toggleFavorite = async () => {
    if (!entry) return
    const updated = await api.updateEntry(entry.id, { is_favorite: !entry.is_favorite })
    setEntry(updated)
    refreshAll()
  }

  const handleDelete = async () => {
    if (!entry) return
    setDeleting(true)
    try {
      await api.deleteEntry(entry.id)
      navigate('/')
    } catch { setDeleting(false) }
  }

  const loadHistory = async () => {
    if (!id) return
    const hist = await api.getHistory(Number(id))
    setHistory(hist)
    setShowHistory(true)
  }

  const restoreVersion = async (historyId: number) => {
    if (!id) return
    const restored = await api.restoreVersion(Number(id), historyId)
    setEntry(restored)
    setShowHistory(false)
    refreshAll()
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowHistory(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Загрузка...</div>
      </div>
    )
  }

  if (!entry) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Запись не найдена</div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {toast && <Toast message={toast} />}

      {/* Top bar */}
      <div className="border-b border-gray-800 px-4 py-2 flex items-center gap-2 bg-gray-900 sticky top-0 z-10">
        <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-200 text-sm px-2 py-1 rounded hover:bg-gray-800">← Назад</button>
        <div className="flex-1" />
        <button onClick={handleCopyTitle} className="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-800" title="Копировать название">📋 Название</button>
        <button onClick={handleCopyContent} className="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-800" title="Копировать всё содержимое">📋 Всё</button>
        <button onClick={() => navigate(`/edit/${entry.id}`)} className="text-sm text-blue-400 hover:text-blue-300 px-3 py-1.5 rounded-lg hover:bg-gray-800">✏ Изменить</button>
        <button onClick={loadHistory} className="text-sm text-gray-400 hover:text-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-800">🕘 История</button>
        <button onClick={toggleFavorite} className={`px-3 py-1.5 rounded-lg text-sm ${entry.is_favorite ? 'bg-yellow-500/20 text-yellow-400' : 'text-gray-400 hover:bg-gray-800'}`}>
          {entry.is_favorite ? '⭐' : '☆'}
        </button>
        {!confirmDelete ? (
          <button onClick={() => setConfirmDelete(true)} className="text-sm text-red-400 hover:text-red-300 px-3 py-1.5 rounded-lg hover:bg-red-950">🗑</button>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-red-400 text-sm">Удалить?</span>
            <button onClick={handleDelete} disabled={deleting} className="bg-red-600 hover:bg-red-500 text-white text-sm px-3 py-1 rounded">Да</button>
            <button onClick={() => setConfirmDelete(false)} className="text-gray-400 text-sm px-2">✕</button>
          </div>
        )}
      </div>

      <div className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-1">{entry.title}</h1>
        <div className="flex flex-wrap items-center gap-3 mb-5 text-xs text-gray-500">
          {entry.category_name && (
            <span className="bg-gray-800 px-2 py-0.5 rounded text-gray-400">{entry.category_name}</span>
          )}
          {entry.tags.map((tag: any) => (
            <span key={tag.id} className="tag-badge">#{tag.name}</span>
          ))}
          <span>Создано: {new Date(entry.created_at).toLocaleDateString('ru-RU')}</span>
          <span>Обновлено: {new Date(entry.updated_at).toLocaleString('ru-RU')}</span>
        </div>

        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 mb-6">
          <MarkdownPreview content={entry.content} />
        </div>

        {entry.attachments && entry.attachments.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-3">Вложения</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {entry.attachments.map((att: any) => (
                <div key={att.id} className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center gap-3">
                  {att.mime_type.startsWith('image/') ? (
                    <img src={`/api/attachments/${att.id}`} alt={att.original_filename} className="w-10 h-10 object-cover rounded" />
                  ) : <span className="text-2xl">📎</span>}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200 truncate">{att.original_filename}</div>
                    <div className="text-xs text-gray-600">{(att.size / 1024).toFixed(1)} KB</div>
                  </div>
                  {att.mime_type.startsWith('image/') ? (
                    <a href={`/api/attachments/${att.id}`} target="_blank" rel="noreferrer" className="text-blue-400 text-xs hover:underline">Открыть</a>
                  ) : (
                    <a href={`/api/attachments/${att.id}`} download={att.original_filename} className="text-blue-400 text-xs hover:underline">Скачать</a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* History modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setShowHistory(false)}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <h2 className="font-semibold text-gray-100">История изменений</h2>
              <button onClick={() => setShowHistory(false)} className="text-gray-500 hover:text-gray-300">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {history.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">История пуста</p>
              ) : (
                history.map((h: HistoryEntry) => (
                  <div key={h.id} className="bg-gray-800 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300 font-medium">{h.title}</span>
                      <span className="text-xs text-gray-500">{new Date(h.created_at).toLocaleString('ru-RU')}</span>
                    </div>
                    <button onClick={() => restoreVersion(h.id)} className="text-xs text-green-400 hover:text-green-300 mt-2">
                      Восстановить эту версию
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
