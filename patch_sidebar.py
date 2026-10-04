# -*- coding: utf-8 -*-
path = r'D:\!AiSite\sysadmin\sysvault\frontend\src\components\Sidebar.tsx'
with open(path, encoding='utf-8') as f:
    content = f.read()

anchor = "          <span>\U0001F558</span> \u0421\u0432\u0435\u0436\u0435\u0435\n        </button>"
idx = content.find('\u0421\u0432\u0435\u0436\u0435\u0435')
print('anchor idx:', idx)
line_end = content.find('</button>', idx)
line_end = content.find('\n', line_end) + 1

addition = '''        <button onClick={() => nav('/assets')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath.startsWith('/assets') ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>\U0001F5A5</span> \u0418\u043d\u0432\u0435\u043d\u0442\u0430\u0440\u044c
        </button>
        <button onClick={() => nav('/employees')}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${currentPath.startsWith('/employees') ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
          <span>\U0001F465</span> \u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0438
        </button>
'''
content = content[:line_end] + addition + content[line_end:]
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Sidebar OK:', "/assets'" in content)
