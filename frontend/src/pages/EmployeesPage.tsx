import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { Employee, Asset } from '../types'

interface EditState {
  id?: number
  full_name: string
  department: string
  position: string
  phone: string
  email: string
  sip: string
  domain_login: string
  room: string
}

const emptyEdit: EditState = {
  full_name: '', department: '', position: '', phone: '', email: '',
  sip: '', domain_login: '', room: '',
}

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [q, setQ] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [assets, setAssets] = useState<Asset[]>([])
  const [edit, setEdit] = useState<EditState | null>(null)
  const [saving, setSaving] = useState(false)
  const [showPicker, setShowPicker] = useState(false)
  const [unassigned, setUnassigned] = useState<Asset[]>([])
  const [pickerQ, setPickerQ] = useState('')

  const loadEmployees = useCallback(() => {
    api.getEmployees(q || undefined).then(setEmployees).catch(() => {})
  }, [q])

  useEffect(() => { loadEmployees() }, [loadEmployees])

  useEffect(() => {
    const t = setTimeout(loadEmployees, 300)
    return () => clearTimeout(t)
  }, [q])

  const loadAssets = useCallback((id: number) => {
    api.getEmployeeAssets(id).then(setAssets).catch(() => setAssets([]))
  }, [])

  useEffect(() => {
    if (selectedId) loadAssets(selectedId)
    else setAssets([])
  }, [selectedId, loadAssets])

  const selected = employees.find(e => e.id === selectedId) || null

  const openEdit = (emp?: Employee) => {
    if (emp) {
      setEdit({
        id: emp.id, full_name: emp.full_name, department: emp.department || '',
        position: emp.position || '', phone: emp.phone || '', email: emp.email || '',
        sip: emp.sip || '', domain_login: emp.domain_login || '', room: emp.room || '',
      })
    } else setEdit({ ...emptyEdit })
  }

  const save = async () => {
    if (!edit) return
    setSaving(true)
    try {
      if (edit.id) await api.updateEmployee(edit.id, edit)
      else {
        const created = await api.createEmployee(edit)
        setSelectedId(created.id)
      }
      setEdit(null)
      loadEmployees()
    } catch { alert('Ошибка сохранения') } finally { setSaving(false) }
  }

  const del = async (id: number) => {
    if (!confirm('Удалить сотрудника? Техника останется без владельца.')) return
    await api.deleteEmployee(id)
    if (selectedId === id) setSelectedId(null)
    loadEmployees()
  }

  const unassign = async (assetId: number) => {
    await api.assignAsset(assetId, null)
    if (selectedId) loadAssets(selectedId)
    loadEmployees()
  }

  const openPicker = async () => {
    const list = await api.getAssets({ unassigned: true })
    setUnassigned(list)
    setPickerQ('')
    setShowPicker(true)
  }

  const assign = async (assetId: number) => {
    if (!selectedId) return
    await api.assignAsset(assetId, selectedId)
    setShowPicker(false)
    loadAssets(selectedId)
    loadEmployees()
  }

  const filteredPicker = pickerQ
    ? unassigned.filter(a => ((a.model || '') + (a.vendor || '') + (a.inventory_number || '')).toLowerCase().includes(pickerQ.toLowerCase()))
    : unassigned

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Левая колонка: список сотрудников */}
      <div className="w-72 min-w-[16rem] border-r border-gray-800 flex flex-col bg-gray-900/40">
        <div className="p-3 border-b border-gray-800 flex items-center gap-2">
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Поиск сотрудника..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-sm text-gray-200" />
          <button onClick={() => openEdit()} className="bg-blue-600 hover:bg-blue-500 text-white px-2 py-1.5 rounded-lg text-sm">+</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {employees.map(emp => (
            <button key={emp.id} onClick={() => setSelectedId(emp.id)}
              className={`w-full text-left px-3 py-2 border-b border-gray-800/50 flex items-center justify-between gap-2 ${selectedId === emp.id ? 'bg-gray-800' : 'hover:bg-gray-800/60'}`}>
              <span className={`text-sm truncate ${selectedId === emp.id ? 'text-gray-100' : 'text-gray-300'}`}>{emp.full_name}</span>
              {emp.asset_count > 0 && (
                <span className="text-xs bg-blue-500/15 text-blue-300 px-1.5 py-0.5 rounded whitespace-nowrap">{emp.asset_count}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Правая колонка: оборудование сотрудника */}
      <div className="flex-1 overflow-y-auto">
        {!selected ? (
          <div className="text-center py-24 text-gray-600 text-sm">
            Выберите сотрудника слева, чтобы увидеть его оборудование
          </div>
        ) : (
          <div>
            <div className="border-b border-gray-800 px-6 py-3 bg-gray-900 flex items-center gap-3 flex-wrap">
              <h2 className="text-lg font-semibold text-gray-100">{selected.full_name}</h2>
              {selected.position && <span className="text-sm text-gray-500">{selected.position}</span>}
              {selected.department && <span className="text-xs bg-gray-800 px-2 py-0.5 rounded text-gray-400">{selected.department}</span>}
              <div className="flex-1" />
              <button onClick={() => openEdit(selected)} className="text-sm text-blue-400 hover:text-blue-300 px-2 py-1 rounded hover:bg-gray-800">✏ Изменить</button>
              <button onClick={() => del(selected.id)} className="text-sm text-red-400 hover:text-red-300 px-2 py-1 rounded hover:bg-red-950">🗑 Удалить</button>
            </div>

            <div className="px-6 py-3 flex flex-wrap gap-4 text-xs text-gray-400 border-b border-gray-800/50">
              {selected.sip && <span>SIP: <span className="font-mono text-gray-300">{selected.sip}</span></span>}
              {selected.phone && <span>Тел: <span className="font-mono text-gray-300">{selected.phone}</span></span>}
              {selected.email && <span>Email: <span className="font-mono text-gray-300">{selected.email}</span></span>}
              {selected.domain_login && <span>Логин: <span className="font-mono text-gray-300">{selected.domain_login}</span></span>}
              {selected.room && <span>Кабинет: <span className="text-gray-300">{selected.room}</span></span>}
            </div>

            <div className="px-6 py-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-400">Закреплённое оборудование ({assets.length})</h3>
                <button onClick={openPicker} className="text-sm bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg">
                  + Привязать технику
                </button>
              </div>
              {assets.length === 0 ? (
                <p className="text-gray-600 text-sm py-8 text-center">За сотрудником не закреплена техника</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
                      <th className="py-2 px-2">Тип</th>
                      <th className="py-2 px-2">Модель</th>
                      <th className="py-2 px-2">Инв. №</th>
                      <th className="py-2 px-2">Серийный</th>
                      <th className="py-2 px-2">Кабинет</th>
                      <th className="py-2 px-2">Статус</th>
                      <th className="py-2 px-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map(a => (
                      <tr key={a.id} className="border-b border-gray-800/50 hover:bg-gray-900/60">
                        <td className="py-2 px-2 text-gray-400 whitespace-nowrap">{a.asset_type}</td>
                        <td className="py-2 px-2 text-gray-100">{[a.vendor, a.model].filter(Boolean).join(' ')}</td>
                        <td className="py-2 px-2 font-mono text-xs text-blue-300">{a.inventory_number || '—'}</td>
                        <td className="py-2 px-2 font-mono text-xs text-gray-500">{a.serial_number || '—'}</td>
                        <td className="py-2 px-2 text-gray-400">{a.location || '—'}</td>
                        <td className="py-2 px-2 text-gray-400 whitespace-nowrap">{a.status}</td>
                        <td className="py-2 px-2">
                          <button onClick={() => unassign(a.id)} className="text-xs text-orange-400 hover:text-orange-300" title="Отвязать">✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Модалка редактирования */}
      {edit && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setEdit(null)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e: any) => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <h3 className="font-semibold text-gray-100">{edit.id ? 'Изменить' : 'Новый'} сотрудник</h3>
              <button onClick={() => setEdit(null)} className="text-gray-500 hover:text-gray-300">✕</button>
            </div>
            <div className="p-4 space-y-3">
              <F label="ФИО *" value={edit.full_name} onChange={(v: string) => setEdit({ ...edit, full_name: v })} />
              <div className="grid grid-cols-2 gap-3">
                <F label="Отдел" value={edit.department} onChange={(v: string) => setEdit({ ...edit, department: v })} />
                <F label="Должность" value={edit.position} onChange={(v: string) => setEdit({ ...edit, position: v })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <F label="Телефон" value={edit.phone} onChange={(v: string) => setEdit({ ...edit, phone: v })} />
                <F label="SIP" value={edit.sip} onChange={(v: string) => setEdit({ ...edit, sip: v })} mono />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <F label="Email" value={edit.email} onChange={(v: string) => setEdit({ ...edit, email: v })} mono />
                <F label="Доменный логин" value={edit.domain_login} onChange={(v: string) => setEdit({ ...edit, domain_login: v })} mono />
              </div>
              <F label="Кабинет" value={edit.room} onChange={(v: string) => setEdit({ ...edit, room: v })} />
              <button onClick={save} disabled={saving}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white py-2 rounded-lg text-sm font-medium">
                {saving ? 'Сохраняю...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка выбора техники */}
      {showPicker && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setShowPicker(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col" onClick={(e: any) => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-800 flex items-center gap-2">
              <h3 className="font-semibold text-gray-100 flex-1">Выберите технику для {selected?.full_name}</h3>
              <button onClick={() => setShowPicker(false)} className="text-gray-500 hover:text-gray-300">✕</button>
            </div>
            <div className="p-3 border-b border-gray-800">
              <input value={pickerQ} onChange={e => setPickerQ(e.target.value)} placeholder="Поиск..."
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200" />
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {filteredPicker.length === 0 ? (
                <p className="text-gray-600 text-sm text-center py-6">Нет свободной техники</p>
              ) : filteredPicker.map(a => (
                <button key={a.id} onClick={() => assign(a.id)}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-800 flex items-center gap-3">
                  <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded whitespace-nowrap">{a.asset_type}</span>
                  <span className="text-sm text-gray-200 flex-1 truncate">{[a.vendor, a.model].filter(Boolean).join(' ')}</span>
                  {a.inventory_number && <span className="font-mono text-xs text-blue-300">{a.inventory_number}</span>}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function F({ label, value, onChange, mono }: { label: string; value: string; onChange: (v: string) => void; mono?: boolean }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input value={value} onChange={(e: any) => onChange(e.target.value)}
        className={`w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 ${mono ? 'font-mono' : ''}`} />
    </div>
  )
}
