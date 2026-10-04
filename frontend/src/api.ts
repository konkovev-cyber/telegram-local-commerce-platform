import type { Entry, Category, Tag, SearchResult, ImportResult, Employee, Asset, InventoryMeta } from './types'

const API = ''

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('sysvault_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API}${path}`, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('sysvault_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  changePassword: (current: string, newPass: string) =>
    request<void>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: current, new_password: newPass }),
    }),

  getEntries: (params?: Record<string, any>) => {
    const qs = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) qs.set(k, String(v))
      })
    }
    const query = qs.toString()
    return request<Entry[]>(`/api/entries${query ? `?${query}` : ''}`)
  },

  getEntry: (id: number) => request<Entry>(`/api/entries/${id}`),

  createEntry: (data: { title: string; content?: string; category_id?: number | null; tags?: string[]; is_favorite?: boolean }) =>
    request<Entry>('/api/entries', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateEntry: (id: number, data: Partial<Entry>) =>
    request<Entry>(`/api/entries/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteEntry: (id: number) =>
    request<void>(`/api/entries/${id}`, { method: 'DELETE' }),

  search: (q: string, limit = 50) =>
    request<SearchResult>(`/api/entries/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  getHistory: (id: number) => request<import('./types').HistoryEntry[]>(`/api/entries/${id}/history`),

  restoreVersion: (id: number, historyId: number) =>
    request<Entry>(`/api/entries/${id}/restore/${historyId}`, { method: 'POST' }),

  importTxt: (content: string, categoryId?: number, separator?: string) =>
    request<ImportResult>('/api/import/txt', {
      method: 'POST',
      body: JSON.stringify({ content, category_id: categoryId, separator }),
    }),

  getCategories: () => request<Category[]>('/api/categories'),

  createCategory: (name: string) =>
    request<Category>('/api/categories', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  updateCategory: (id: number, name: string) =>
    request<Category>(`/api/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ name }),
    }),

  deleteCategory: (id: number, newCategoryId?: number) =>
    request<void>(`/api/categories/${id}${newCategoryId ? `?new_category_id=${newCategoryId}` : ''}`, {
      method: 'DELETE',
    }),

  getTags: () => request<Tag[]>('/api/tags'),

  uploadAttachment: (entryId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const token = localStorage.getItem('sysvault_token')
    return fetch(`/api/entries/${entryId}/attachments`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(r => {
      if (!r.ok) throw new Error('Upload failed')
      return r.json()
    })
  },

  deleteAttachment: (id: number) =>
    request<void>(`/api/attachments/${id}`, { method: 'DELETE' }),

  listBackups: () =>
    request<{ filename: string; size: number; created_at: string }[]>('/api/backups'),

  createBackup: () =>
    request<{ path: string; filename: string }>('/api/backups', { method: 'POST' }),

  exportJson: () =>
    request<string>('/api/export/json'),

  exportMarkdown: () =>
    request<Record<string, string[]>>('/api/export/markdown'),

  health: () => request<{ status: string }>('/api/health'),

  getMeta: () =>
    request<InventoryMeta>('/api/meta'),

  getEmployees: (q?: string) =>
    request<Employee[]>(`/api/employees${q ? `?q=${encodeURIComponent(q)}` : ''}`),

  createEmployee: (data: Partial<Employee>) =>
    request<{ id: number }>('/api/employees', { method: 'POST', body: JSON.stringify(data) }),

  updateEmployee: (id: number, data: Partial<Employee>) =>
    request<{ id: number }>(`/api/employees/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  deleteEmployee: (id: number) =>
    request<void>(`/api/employees/${id}`, { method: 'DELETE' }),

  getEmployeeAssets: (id: number) =>
    request<Asset[]>(`/api/employees/${id}/assets`),

  getAssets: (params?: Record<string, any>) => {
    const qs = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
      })
    }
    const query = qs.toString()
    return request<Asset[]>(`/api/assets${query ? `?${query}` : ''}`)
  },

  createAsset: (data: Partial<Asset>) =>
    request<{ id: number }>('/api/assets', { method: 'POST', body: JSON.stringify(data) }),

  updateAsset: (id: number, data: Partial<Asset>) =>
    request<{ id: number }>(`/api/assets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  deleteAsset: (id: number) =>
    request<void>(`/api/assets/${id}`, { method: 'DELETE' }),

  assignAsset: (assetId: number, employeeId: number | null) =>
    request<{ ok: boolean }>(
      employeeId === null
        ? `/api/assets/${assetId}/unassign`
        : `/api/assets/${assetId}/assign/${employeeId}`,
      { method: 'POST' },
    ),

  importInventory: (text: string, defaultType?: string) =>
    request<{ created: number; employees_created: number; errors: string[] }>('/api/inventory/import', {
      method: 'POST',
      body: JSON.stringify({ text, default_type: defaultType }),
    }),
}
