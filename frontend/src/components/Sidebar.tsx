import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Sidebar() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<any[]>([])
  const [tags, setTags] = useState<any[]>([])
  const [newCatName, setNewCatName] = useState('')
  const [showNewCat, setShowNewCat] = useState(false)
  const [showChangePass, setShowChangePass] = useState(false)
  const [currPwd, setCurrPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [pwdMsg, setPwdMsg] = useState('')
  const [pwdErr, setPwdErr] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getCategories(), api.getTags()])
      .then(([cats, t]) => { setCategories(cats); setTags(t) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleCreateCategory = async () => {
    if (!newCatName.trim()) return
    try {
      await api.createCategory(newCatName.trim())
      setNewCatName('')
      setShowNewCat(false)
      const cats = await api.getCategories()
      setCategories(cats)
    } catch (e) { console.error(e) }
  }

  const handleChangePassword = async () => {
    setPwdMsg('')
    setPwdErr('')
    try {
      await api.changePassword(currPwd, newPwd)
      setPwdMsg('Пароль изменён')
      setCurrPwd('')
      setNewPwd('')
      setShowChangePass(false)
    } catch (e: any) {
      setPwdErr(e.message || 'Ошибка')
    }
  }

  const nav = (path: string) => navigate(path)
  const currentPath = typeof window !== 'undefined' ? window.location.pathname : '/'

  return (
    <div className="w-56 min-w-[14rem] flex flex-col h-full bg-gray-900 border-r border-gray-800">
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-blue-400 text-xl">🔐</span>
          <h1 className="text-lg font-bold text-gray-100">Уголок сисадмина</h1>
        </div>
        <p className="text-xs text-gray-500 mt-1">База знаний</p>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <button onClick={() => nav('/')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath === '/' ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>📋</span> Все записи
        </button>
        <button onClick={() => nav('/favorites')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath === '/favorites' ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>⭐</span> Избранное
        </button>
        <button onClick={() => nav('/recent')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath === '/recent' ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>🕘</span> Свежее
        </button>
        <button onClick={() => nav('/assets')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath.startsWith('/assets') ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>🖥</span> Инвентарь
        </button>
        <button onClick={() => nav('/employees')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath.startsWith('/employees') ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>👥</span> Сотрудники
        </button>

        <div className="mt-4 mb-2 px-3 text-xs text-gray-500 uppercase tracking-wider">Категории</div>
        {loading ? (
          <div className="px-3 py-1 text-xs text-gray-600">Загрузка...</div>
        ) : categories.map((cat: any) => (
          <button key={cat.id} onClick={() => nav(`/category/${cat.id}`)}
            className={`w-full text-left px-3 py-1.5 rounded-lg text-sm flex items-center justify-between ${currentPath === `/category/${cat.id}` ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
            <span>{cat.name}</span>
            <span className="text-xs text-gray-600">{cat.entry_count}</span>
          </button>
        ))}

        {showNewCat ? (
          <div className="px-3 py-1 flex gap-1">
            <input value={newCatName} onChange={e => setNewCatName(e.target.value)} placeholder="Название..."
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 outline-none"
              onKeyDown={e => e.key === 'Enter' && handleCreateCategory()} autoFocus />
            <button onClick={handleCreateCategory} className="text-green-400 text-sm">✓</button>
            <button onClick={() => setShowNewCat(false)} className="text-gray-500 text-sm">✕</button>
          </div>
        ) : (
          <button onClick={() => setShowNewCat(true)}
            className="w-full text-left px-3 py-1.5 rounded-lg text-sm text-gray-500 hover:bg-gray-800 hover:text-gray-300">
            + Категория
          </button>
        )}

        <div className="mt-4 mb-2 px-3 text-xs text-gray-500 uppercase tracking-wider">Теги</div>
        {tags.slice(0, 15).map((tag: any) => (
          <button key={tag.id} onClick={() => nav(`/tag/${tag.name}`)}
            className="w-full text-left px-3 py-1.5 rounded-lg text-sm flex items-center gap-2 text-gray-400 hover:bg-gray-800 hover:text-gray-200">
            <span className="tag-badge">#{tag.name}</span>
          </button>
        ))}
      </div>

      <div className="p-3 border-t border-gray-800 space-y-1">
        <button onClick={() => nav('/backup')}
          className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200 flex items-center gap-2">
          <span>💾</span> Резервная копия
        </button>
        <button onClick={() => nav('/export')}
          className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200 flex items-center gap-2">
          <span>📤</span> Экспорт
        </button>
        <button onClick={() => setShowChangePass(!showChangePass)}
          className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-200 flex items-center gap-2">
          <span>🔑</span> Сменить пароль
        </button>
        <button onClick={() => { localStorage.removeItem('sysvault_token'); window.location.href = '/login' }}
          className="w-full text-left px-3 py-2 rounded-lg text-sm text-red-400 hover:bg-red-950 hover:text-red-300 flex items-center gap-2">
          <span>🚪</span> Выход
        </button>
      </div>

      {showChangePass && (
        <div className="mx-3 mb-3 bg-gray-800 rounded-lg p-3 space-y-2">
          <input value={currPwd} onChange={e => setCurrPwd(e.target.value)} type="password" placeholder="Текущий пароль"
            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 outline-none" />
          <input value={newPwd} onChange={e => setNewPwd(e.target.value)} type="password" placeholder="Новый пароль"
            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 outline-none" />
          {pwdMsg && <p className="text-green-400 text-xs">{pwdMsg}</p>}
          {pwdErr && <p className="text-red-400 text-xs">{pwdErr}</p>}
          <button onClick={handleChangePassword}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white text-sm py-1.5 rounded">Сохранить</button>
        </div>
      )}
    </div>
  )
}
