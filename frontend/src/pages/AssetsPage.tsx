import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { Asset, Employee, InventoryMeta } from '../types'

const STATUS_COLORS: Record<string, string> = {
  'в работе': 'bg-green-500/15 text-green-400 border-green-500/30',
  'в ремонте': 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  'на складе': 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  'списано': 'bg-red-500/15 text-red-400 border-red-500/30',
}

interface EditState {
  id?: number
  asset_type: string
  vendor: string
  model: string
  serial_number: string
  inventory_number: string
  mac_address: string
  ip_address: string
  status: string
  location: string
  employee_id: number | null
  notes: string
}

const emptyEdit: EditState = {
  asset_type: 'ПК', vendor: '', model: '', serial_number: '', inventory_number: '',
  mac_address: '', ip_address: '', status: 'в работе', location: '',
  employee_id: null, notes: '',
}

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [meta, setMeta] = useState<InventoryMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [fType, setFType] = useState('')
  const [fStatus, setFStatus] = useState('')
  const [fQ, setFQ] = useState('')
  const [fUnassigned, setFUnassigned] = useState(false)
  const [edit, setEdit] = useState<EditState | null>(null)
  const [saving, setSaving] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [importText, setImportText] = useState('')
  const [importMsg, setImportMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = {}
      if (fType) params.type = fType
      if (fStatus) params.status = fStatus
      if (fQ) params.q = fQ
      if (fUnassigned) params.unassigned = true
      setAssets(await api.getAssets(params))
    } catch { } finally { setLoading(false) }
  }, [fType, fStatus, fQ, fUnassigned])

  useEffect(() => {
    api.getMeta().then(setMeta).catch(() => {})
    api.getEmployees().then(setEmployees).catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(load, 250)
    return () => clearTimeout(t)
  }, [load])

  const openEdit = (a?: Asset) => {
    if (a) {
      setEdit({
        id: a.id, asset_type: a.asset_type, vendor: a.vendor || '', model: a.model || '',
        serial_number: a.serial_number || '', inventory_number: a.inventory_number || '',
        mac_address: a.mac_address || '', ip_address: a.ip_address || '',
        status: a.status, location: a.location || '', employee_id: a.employee_id, notes: a.notes || '',
      })
    } else setEdit({ ...emptyEdit })
  }

  const save = async () => {
    if (!edit) return
    setSaving(true)
    try {
      if (edit.id) await api.updateAsset(edit.id, edit)
      else await api.createAsset(edit)
      setEdit(null); load()
    } catch { alert('Ошибка сохранения') } finally { setSaving(false) }
  }

  const del = async (id: number) => {
    if (!confirm('Удалить единицу техники?')) return
    await api.deleteAsset(id); load()
  }

  const doImport = async () => {
    setImportMsg('Импорт...')
    try {
      const res = await api.importInventory(importText)
      setImportMsg(`Создано: ${res.created}, сотрудников: ${res.employees_created}` + (res.errors.length ? `, ошибок: ${res.errors.length}` : ''))
      setImportText(''); load()
    } catch (e: any) { setImportMsg('Ошибка: ' + e.message) }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="border-b border-gray-800 px-6 py-4 bg-gray-900">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-100">Инвентарь</h2>
          <div className="flex-1" />
          <select value={fType} onChange={e => setFType(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-sm text-gray-200">
            <option value="">Все типы</option>
            {meta?.types.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={fStatus} onChange={e => setFStatus(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-sm text-gray-200">
            <option value="">Все статусы</option>
            {meta?.statuses.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input value={fQ} onChange={e => setFQ(e.target.value)} placeholder="Поиск: SN, инв№, MAC, модель..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 w-56" />
          <label className="flex items-center gap-1 text-sm text-gray-400 cursor-pointer">
            <input type="checkbox" checked={fUnassigned} onChange={e => setFUnassigned(e.target.checked)} />
            без владельца
          </label>
          <button onClick={() => setShowImport(!showImport)} className="text-sm text-gray-400 hover:text-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-800">Импорт</button>
          <button onClick={() => openEdit()} className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium">+ Техника</button>
        </div>
      </div>
      {showImport && (
        <div className="mx-6 mt-4 bg-gray-900 border border-gray-700 rounded-xl p-4">
          <p className="text-xs text-gray-500 mb-2">Формат (разделитель ; или таб): ФИО;Должность;Телефон;Email;SIP;Инв.№;Тип;Производитель;Модель;Серийный;MAC;Кабинет</p>
          <textarea value={importText} onChange={e => setImportText(e.target.value)} placeholder="Вставьте строки из таблицы..."
            className="w-full h-32 bg-gray-800 border border-gray-700 rounded-lg p-2 text-xs text-gray-200 font-mono resize-none" />
          <div className="flex items-center gap-3 mt-2">
            <button onClick={doImport} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded-lg text-sm">Импортировать</button>
            {importMsg && <span className="text-sm text-green-400">{importMsg}</span>}
          </div>
        </div>
      )}
      <AssetTable assets={assets} loading={loading} onEdit={openEdit} onDelete={del} />
      {edit && (
        <AssetModal edit={edit} setEdit={setEdit} employees={employees} meta={meta}
          saving={saving} onSave={save} onClose={() => setEdit(null)} />
      )}
    </div>
  )
}

function AssetTable({ assets, loading, onEdit, onDelete }: {
  assets: Asset[]; loading: boolean
  onEdit: (a: Asset) => void; onDelete: (id: number) => void
}) {
  if (loading) return <div className="text-gray-500 text-center py-20">Загрузка...</div>
  if (assets.length === 0) return (
    <div className="text-center py-20">
      <div className="text-4xl mb-4 opacity-30">🖥</div>
      <p className="text-gray-400 text-lg">Техники пока нет</p>
      <p className="text-gray-600 text-sm mt-1">Добавьте первую единицу или импортируйте из таблицы</p>
    </div>
  )
  return (
    <div className="p-6 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
            <th className="py-2 px-2">Тип</th>
            <th className="py-2 px-2">Модель</th>
            <th className="py-2 px-2">Инв. №</th>
            <th className="py-2 px-2">Серийный</th>
            <th className="py-2 px-2">MAC / IP</th>
            <th className="py-2 px-2">Кабинет</th>
            <th className="py-2 px-2">Сотрудник</th>
            <th className="py-2 px-2">Статус</th>
            <th className="py-2 px-2"></th>
          </tr>
        </thead>
        <tbody>
          {assets.map(a => (
            <tr key={a.id} className="border-b border-gray-800/50 hover:bg-gray-900/60">
              <td className="py-2 px-2 text-gray-300 whitespace-nowrap">{a.asset_type}</td>
              <td className="py-2 px-2 text-gray-100">{[a.vendor, a.model].filter(Boolean).join(' ')}</td>
              <td className="py-2 px-2 font-mono text-xs text-blue-300">{a.inventory_number || '—'}</td>
              <td className="py-2 px-2 font-mono text-xs text-gray-400">{a.serial_number || '—'}</td>
              <td className="py-2 px-2 font-mono text-xs text-gray-500">{a.mac_address || a.ip_address || '—'}</td>
              <td className="py-2 px-2 text-gray-400">{a.location || '—'}</td>
              <td className="py-2 px-2 text-gray-300">{a.employee_name || <span className="text-gray-600">—</span>}</td>
              <td className="py-2 px-2">
                <span className={`px-2 py-0.5 rounded text-xs border ${STATUS_COLORS[a.status] || 'bg-gray-800 text-gray-300 border-gray-700'}`}>{a.status}</span>
              </td>
              <td className="py-2 px-2 whitespace-nowrap">
                <button onClick={() => onEdit(a)} className="text-blue-400 hover:text-blue-300 text-xs mr-2">✏</button>
                <button onClick={() => onDelete(a.id)} className="text-red-400 hover:text-red-300 text-xs">🗑</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AssetModal({ edit, setEdit, employees, meta, saving, onSave, onClose }: any) {
  const set = (k: string, v: any) => setEdit({ ...edit, [k]: v })
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e: any) => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="font-semibold text-gray-100">{edit.id ? 'Изменить' : 'Новая'} техника</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Тип</label>
              <select value={edit.asset_type} onChange={(e: any) => set('asset_type', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200">
                {(meta?.types || []).map((t: string) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Статус</label>
              <select value={edit.status} onChange={(e: any) => set('status', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200">
                {(meta?.statuses || []).map((s: string) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Производитель" value={edit.vendor} onChange={(v: string) => set('vendor', v)} />
            <Field label="Модель" value={edit.model} onChange={(v: string) => set('model', v)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Инвентарный №" value={edit.inventory_number} onChange={(v: string) => set('inventory_number', v)} mono />
            <Field label="Серийный №" value={edit.serial_number} onChange={(v: string) => set('serial_number', v)} mono />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="MAC адрес" value={edit.mac_address} onChange={(v: string) => set('mac_address', v)} mono />
            <Field label="IP адрес" value={edit.ip_address} onChange={(v: string) => set('ip_address', v)} mono />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Кабинет / место" value={edit.location} onChange={(v: string) => set('location', v)} />
            <div>
              <label className="block text-xs text-gray-500 mb-1">Сотрудник</label>
              <select value={edit.employee_id ?? ''} onChange={(e: any) => set('employee_id', e.target.value ? Number(e.target.value) : null)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200">
                <option value="">— не закреплён —</option>
                {employees.map((emp: Employee) => <option key={emp.id} value={emp.id}>{emp.full_name}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Заметки</label>
            <textarea value={edit.notes} onChange={(e: any) => set('notes', e.target.value)} rows={2}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 resize-none" />
          </div>
          <button onClick={onSave} disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white py-2 rounded-lg text-sm font-medium">
            {saving ? 'Сохраняю...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, mono }: { label: string; value: string; onChange: (v: string) => void; mono?: boolean }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input value={value} onChange={(e: any) => onChange(e.target.value)}
        className={`w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 ${mono ? 'font-mono' : ''}`} />
    </div>
  )
}
