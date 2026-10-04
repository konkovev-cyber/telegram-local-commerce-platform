# -*- coding: utf-8 -*-
import re

def fix(path):
    with open(path, encoding='utf-8') as f:
        c = f.read()
    # find literal sequences like \U0001F5A5 (backslash + U + 8 hex)
    pattern = re.compile(r'\\U([0-9A-Fa-f]{8})')
    def rep(m):
        return chr(int(m.group(1), 16))
    c2, n = pattern.subn(rep, c)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c2)
    print(path.split(chr(92))[-1], 'replaced:', n)

fix(r'D:\!AiSite\sysadmin\sysvault\frontend\src\pages\AssetsPage.tsx')
fix(r'D:\!AiSite\sysadmin\sysvault\frontend\src\pages\EmployeesPage.tsx')
