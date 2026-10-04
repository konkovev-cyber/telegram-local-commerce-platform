import { useState, useEffect } from 'react'
import { api } from '../api'

export default function BackupPage() {
  const [backups, setBackups] = useState<{ filename: string; size: number; created_at: string }[]>([])
  const [creating, setCreating] = useState(false)
  const [msg, setMsg] = useState('')

  const loadBackups = async () => {
    try {
      const data = await api.listBackups()
      setBackups(data)
    } catch { }
  }

  useEffect(() => { loadBackups() }, [])

  const handleBackup = async () => {
    setCreating(true)
    setMsg('')
    try {
      await api.createBackup()
      setMsg('Резервная копия создана!')
      loadBackups()
    } catch (e: any) {
      setMsg(e.message || 'Ошибка')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-xl font-semibold text-gray-100 mb-6">Резервное копирование</h2>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
          <h3 className="text-gray-200 font-medium mb-2">Создать копию</h3>
          <p className="text-gray-500 text-sm mb-4">
            Создаёт ZIP-архив с базой данных и всеми вложениями.
          </p>
          <button
            onClick={handleBackup}
            disabled={creating}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {creating ? 'Создаю...' : 'Создать копию'}
          </button>
          {msg && <p className="text-sm mt-2 text-green-400">{msg}</p>}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-gray-200 font-medium mb-4">Существующие копии</h3>
          {backups.length === 0 ? (
            <p className="text-gray-600 text-sm">Пока нет копий</p>
          ) : (
            <div className="space-y-2">
              {backups.map(b => (
                <div key={b.filename} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
                  <div>
                    <div className="text-sm text-gray-200">{b.filename}</div>
                    <div className="text-xs text-gray-500">{new Date(b.created_at).toLocaleString('ru-RU')} · {(b.size / 1024).toFixed(1)} KB</div>
                  </div>
                  <a
                    href={`/api/backups/${encodeURIComponent(b.filename)}`}
                    download
                    className="text-blue-400 text-sm hover:text-blue-300"
                  >
                    Скачать
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-gray-200 font-medium mb-2">Восстановление</h3>
          <p className="text-gray-500 text-sm mb-4">
            Остановите контейнеры, замените <code className="text-yellow-400 bg-gray-800 px-1 rounded">data/database.db</code> и <code className="text-yellow-400 bg-gray-800 px-1 rounded">data/attachments/</code> из архива, затем перезапустите.
          </p>
        </div>
      </div>
    </div>
  )
}
