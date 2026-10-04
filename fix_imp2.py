# -*- coding: utf-8 -*-
path = r'D:\!AiSite\sysadmin\sysvault\imp_assets2.py'
with open(path, encoding='utf-8') as f:
    c = f.read()
c = c.replace('for loc, addr, model, sn, inv, resp, atype in PHONES:',
              'for loc, addr, model, sn, inv, resp in PHONES:')
c = c.replace("atype = 'IP-\u0442\u0435\u043b\u0435\u0444\u043e\u043d' if 'Yealink' in model else '\u0410\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0442\u0435\u043b\u0435\u0444\u043e\u043d'",
              "atype = 'IP-\u0442\u0435\u043b\u0435\u0444\u043e\u043d' if 'Yealink' in model else '\u0410\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0442\u0435\u043b\u0435\u0444\u043e\u043d'\n    atype = atype")
with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
print('patched OK')
