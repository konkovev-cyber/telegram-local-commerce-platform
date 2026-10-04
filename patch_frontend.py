# -*- coding: utf-8 -*-
"""Patch frontend files for inventory module."""
import re

FE = r'D:\!AiSite\sysadmin\sysvault\frontend\src'

# ---------- api.ts ----------
path = FE + r'\api.ts'
with open(path, encoding='utf-8') as f:
    content = f.read()

old_import = "import type { Entry, Category, Tag, SearchResult, ImportResult } from './types'"
new_import = "import type { Entry, Category, Tag, SearchResult, ImportResult, Employee, Asset, InventoryMeta } from './types'"
content = content.replace(old_import, new_import)

old_health = "  health: () => request<{ status: string }>('/api/health'),\n}"
new_health = '''  health: () => request<{ status: string }>('/api/health'),

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

  importInventory: (text: string, defaultType?: string) =>
    request<{ created: number; employees_created: number; errors: string[] }>('/api/inventory/import', {
      method: 'POST',
      body: JSON.stringify({ text, default_type: defaultType }),
    }),
}'''
content = content.replace(old_health, new_health)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('api.ts OK:', 'getAssets' in content)

# ---------- Sidebar ----------
path = FE + r'\components\Sidebar.tsx'
with open(path, encoding='utf-8') as f:
    content = f.read()

anchor = '<span>\U0001F55E</span> Свежее\n        </button>'
addition = anchor + '''
        <button onClick={() => nav('/assets')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath.startsWith('/assets') ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>\U0001F5A5</span> Инвентарь
        </button>
        <button onClick={() => nav('/employees')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath.startsWith('/employees') ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>\U0001F465</span> Сотрудники
        </button>'''
content = content.replace(anchor, addition)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Sidebar OK:', '/assets' in content)

# ---------- App.tsx routes ----------
path = FE + r'\App.tsx'
with open(path, encoding='utf-8') as f:
    content = f.read()

imp_anchor = "import ExportPage from './pages/ExportPage'"
content = content.replace(imp_anchor, imp_anchor + "\nimport AssetsPage from './pages/AssetsPage'\nimport EmployeesPage from './pages/EmployeesPage'")

route_anchor = "      <Route path=\"/export\" element={\n        <MainLayout><ExportPage /></MainLayout>\n      } />"
route_add = route_anchor + '''
      <Route path="/assets" element={
        <MainLayout><AssetsPage /></MainLayout>
      } />
      <Route path="/employees" element={
        <MainLayout><EmployeesPage /></MainLayout>
      } />'''
content = content.replace(route_anchor, route_add)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('App OK:', 'AssetsPage' in content)
