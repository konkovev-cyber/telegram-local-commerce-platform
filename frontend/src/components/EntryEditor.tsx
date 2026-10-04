import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import MarkdownPreview from './MarkdownPreview'
import type { Attachment } from '../types'

interface Props {
  entryId?: number
  categoryId?: number
  onBack?: () => void
}

export default function EntryEditor({ entryId, categoryId, onBack }: Props) {
  const navigate = useNavigate()
  const isEdit = !!entryId

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<number | undefined>(categoryId ?? undefined)
  const [tagsInput, setTagsInput] = useState('')
  const [tagSuggestions, setTagSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [isFavorite, setIsFavorite] = useState(false)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState<'edit' | 'preview'>('edit')
  const [allTags, setAllTags] = useState<string[]>([])
  const tagsRef = React.useRef<HTMLDivElement>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    api.getTags().then(tags => setAllTags(tags.map((t: any) => t.name))).catch(() => {})
    if (entryId) {
      api.getEntry(entryId).then(entry => {
        setTitle(entry.title)
        setContent(entry.content)
        setSelectedCategory(entry.category_id ?? undefined)
        setIsFavorite(entry.is_favorite)
        setAttachments(entry.attachments)
        setTagsInput(entry.tags.map((t: any) => t.name).join(', '))
      }).catch(() => navigate('/'))
    } else if (categoryId) {
      setSelectedCategory(categoryId)
    }
  }, [entryId, categoryId])

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (tagsRef.current && !tagsRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const parseTags = (input: string): string[] => {
    return input.split(/[,#\s]+/).map(t => t.trim().toLowerCase()).filter(Boolean)
  }

  React.useEffect(() => {
    const tags = parseTags(tagsInput)
    const last = tags[tags.length - 1] || ''
    if (last) {
      const matches = allTags.filter(t => t.includes(last) && !tags.includes(t))
      setTagSuggestions(matches)
      setShowSuggestions(matches.length > 0)
    } else {
      setTagSuggestions([])
      setShowSuggestions(false)
    }
  }, [tagsInput, allTags])

  const handleSave = async () => {
    if (!title.trim()) { setError('Название обязательно'); return }
    setSaving(true)
    setError('')
    try {
      const finalTags = [...new Set(parseTags(tagsInput))]
      if (isEdit) {
        await api.updateEntry(entryId!, { title: title.trim(), content, category_id: selectedCategory ?? null, is_favorite: isFavorite, tags: finalTags as any })
        navigate(`/entry/${entryId}`)
      } else {
        const entry = await api.createEntry({ title: title.trim(), content, category_id: selectedCategory ?? null, is_favorite: isFavorite, tags: finalTags as any })
        navigate(`/entry/${entry.id}`)
      }
    } catch (e: any) {
      setError(e.message || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files?.length) return
    for (const file of files) {
      try {
        const id = entryId || (await api.createEntry({ title: 'Без названия', content: '', tags: [] })).id
        const att = await api.uploadAttachment(id, file) as Attachment
        setAttachments(prev => [...prev, att])
        if (!entryId) {
          navigate(`/entry/${id}`)
        }
      } catch (err) {
        console.error('Ошибка загрузки', err)
      }
    }
    e.target.value = ''
  }

  const handleDeleteAttachment = async (attId: number) => {
    await api.deleteAttachment(attId)
    setAttachments(prev => prev.filter((a: Attachment) => a.id !== attId))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      handleSave()
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden" onKeyDown={handleKeyDown}>
      <div className="border-b border-gray-800 px-4 py-2 flex items-center gap-3 bg-gray-900">
        {onBack && (
          <button onClick={onBack} className="text-gray-400 hover:text-gray-200 text-sm">← Назад</button>
        )}
        <div className="flex-1" />
        <button onClick={() => setViewMode(viewMode === 'edit' ? 'preview' : 'edit')}
          className="text-sm text-gray-400 hover:text-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-800">
          {viewMode === 'edit' ? '👁 Предпросмотр' : '✏ Редактировать'}
        </button>
        <button onClick={() => setIsFavorite(!isFavorite)}
          className={`px-3 py-1.5 rounded-lg text-sm ${isFavorite ? 'bg-yellow-500/20 text-yellow-400' : 'text-gray-400 hover:bg-gray-800'}`}>
          {isFavorite ? '⭐ В избранном' : '☆ В избранное'}
        </button>
        <button onClick={handleSave} disabled={saving}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-4 py-1.5 rounded-lg text-sm font-medium">
          {saving ? 'Сохраняю...' : 'Сохранить'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          <input type="text" value={title} onChange={e => setTitle(e.target.value)}
            placeholder="Название записи..."
            className="w-full bg-transparent text-2xl font-bold text-gray-100 outline-none placeholder-gray-600 border-b border-gray-800 pb-2" />

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex flex-wrap gap-3">
            <select value={selectedCategory ?? ''} onChange={e => setSelectedCategory(e.target.value ? Number(e.target.value) : undefined)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none">
              <option value="">Без категории</option>
            </select>

            <div ref={tagsRef} className="relative flex-1 min-w-[200px]">
              <input type="text" value={tagsInput}
                onChange={e => { setTagsInput(e.target.value); setShowSuggestions(true) }}
                onFocus={() => setShowSuggestions(true)}
                placeholder="Теги (через запятую или пробел)..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none placeholder-gray-500" />
              {showSuggestions && tagSuggestions.length > 0 && (
                <div className="absolute z-50 top-full left-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl max-h-40 overflow-y-auto min-w-[200px]">
                  {tagSuggestions.map(tag => (
                    <button key={tag} onMouseDown={() => { setTagsInput(prev => prev ? prev + ', ' + tag : tag); setShowSuggestions(false) }}
                      className="w-full text-left px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800">
                      #{tag}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {viewMode === 'edit' ? (
            <textarea value={content} onChange={e => setContent(e.target.value)}
              placeholder="Пишите в Markdown..."
              className="w-full h-96 bg-gray-900 border border-gray-800 rounded-lg p-4 text-sm text-gray-200 outline-none focus:border-blue-500 font-mono resize-none" />
          ) : (
            <div className="w-full h-96 bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-y-auto">
              {content ? <MarkdownPreview content={content} /> : <p className="text-gray-600 text-sm">Пусто</p>}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-400">Вложения</h3>
              <label className="text-xs text-blue-400 hover:text-blue-300 cursor-pointer">
                + Добавить файл
                <input ref={fileInputRef} type="file" className="hidden" multiple onChange={handleUpload} />
              </label>
            </div>
            {attachments.length === 0 ? (
              <p className="text-gray-600 text-sm italic">Нет вложений</p>
            ) : (
              <div className="space-y-1">
                {attachments.map((att: Attachment) => (
                  <div key={att.id} className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
                    <span className="text-gray-400 text-sm flex-1 truncate">{att.original_filename}</span>
                    <span className="text-gray-600 text-xs">{(att.size / 1024).toFixed(1)} KB</span>
                    {att.mime_type.startsWith('image/') ? (
                      <a href={`/api/attachments/${att.id}`} target="_blank" rel="noreferrer" className="text-blue-400 text-xs hover:underline">Открыть</a>
                    ) : (
                      <a href={`/api/attachments/${att.id}`} download={att.original_filename} className="text-blue-400 text-xs hover:underline">Скачать</a>
                    )}
                    <button onClick={() => handleDeleteAttachment(att.id)} className="text-red-400 text-xs hover:text-red-300">✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
