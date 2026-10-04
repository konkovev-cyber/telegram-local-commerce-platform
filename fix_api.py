# -*- coding: utf-8 -*-
path = r'D:\!AiSite\sysadmin\sysvault\frontend\src\api.ts'
with open(path, encoding='utf-8') as f:
    c = f.read()

if 'assignAsset' not in c:
    anchor = "  importInventory: (text: string, defaultType?: string) =>"
    add = '''  assignAsset: (assetId: number, employeeId: number | null) =>
    request<{ ok: boolean }>(
      employeeId === null
        ? `/api/assets/${assetId}/unassign`
        : `/api/assets/${assetId}/assign/${employeeId}`,
      { method: 'POST' },
    ),

  importInventory: (text: string, defaultType?: string) =>'''
    c = c.replace(anchor, add)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
print('assignAsset added:', 'assignAsset' in c)
