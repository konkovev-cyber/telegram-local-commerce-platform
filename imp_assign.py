# -*- coding: utf-8 -*-
import requests

BASE = 'http://192.168.100.222:9000'
r = requests.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin'}, timeout=10)
H = {'Authorization': 'Bearer ' + r.json()['access_token'], 'Content-Type': 'application/json'}

# Сотрудники центрального офиса (из таблицы инвентаризации)
OFFICE = ['Попандопуло', 'Колесникова', 'Кичигина', 'Маслий', 'Негода', 'Базалий',
          'Агамалян', 'Ловкова', 'Бычков', 'Кривоносов', 'Ковалев', 'Призов', 'Штефан',
          'Толкунов', 'Попова', 'Исламова', 'Костенко', 'Веренич', 'Волк', 'Перекопская',
          'Антохина', 'Андреев', 'Бурнашкин', 'Потапов', 'Белова', 'Кравченко',
          'Быстрицкий', 'Асриев', 'Гаспарян', 'Дудоладов', 'Долгов', 'Серотенко', 'Горобец', 'Баканов']

ids = {}
existing = requests.get(f'{BASE}/api/employees', headers=H, timeout=10).json()
by_surname = {}
for e in existing:
    surname = e['full_name'].split()[0]
    by_surname[surname] = e['id']

for s in OFFICE:
    if s in by_surname:
        ids[s] = by_surname[s]
        continue
    resp = requests.post(f'{BASE}/api/employees', headers=H, timeout=10,
                         json={'full_name': s, 'department': 'Центральный офис'})
    if resp.status_code == 201:
        ids[s] = resp.json()['id']
print('office employees:', len(ids))

# (тип, модель, инв№, сотрудник) — привязка
ASSIGN = [
    ('МФУ/Принтер', 'Canon MF421dw', '251', 'Попандопуло'),
    ('МФУ/Принтер', 'Canon MF421dw', '261', 'Колесникова'),
    ('МФУ/Принтер', 'Canon MF421dw', '89', 'Кичигина'),
    ('МФУ/Принтер', 'Canon MF421dw', '250', 'Маслий'),
    ('МФУ/Принтер', 'Canon MF421dw', '249', 'Негода'),
    ('МФУ/Принтер', 'Canon MF443dw', '00-000949', 'Базалий'),
    ('МФУ/Принтер', 'Canon MF4730', '2', 'Агамалян'),
    ('МФУ/Принтер', 'Canon MF6140dn', '55н', 'Ловкова'),
    ('МФУ/Принтер', 'Canon MF6140dn', '222', 'Бычков'),
    ('МФУ/Принтер', 'Canon MF6140dn', '221', 'Кривоносов'),
    ('МФУ/Принтер', 'Canon MF6140dn', '57н', 'Ковалев'),
    ('МФУ/Принтер', 'Kyocera P2040DN', '00-000888', 'Призов'),
    ('ИБП', 'APC BC500RS', '17Н', 'Штефан'),
    ('ИБП', 'APC BC500RS', '16H', 'Толкунов'),
    ('ИБП', 'APC BK500-RS', '33л', 'Попова'),
    ('ИБП', 'APC BK500-RS', '18Н', 'Исламова'),
    ('ИБП', 'APC BX1100-CI-RS', '68', 'Призов'),
    ('ИБП', 'APC BX1100-CI-RS', '119', 'Колесникова'),
    ('ИБП', 'APC BX1100-CI-RS', '37', 'Волк'),
    ('ИБП', 'APC BX1100-CI-RS', '21', 'Перекопская'),
    ('ИБП', 'APC BX1100-CI-RS', '126', 'Антохина'),
    ('ИБП', 'APC BX1100-CI-RS', '185', 'Андреев'),
    ('ИБП', 'Ippon BCP600', '490', 'Бычков'),
    ('ИБП', 'Ippon BCP600', '488', 'Потапов'),
    ('ИБП', 'Ippon BCP600', '492', 'Белова'),
    ('ИБП', 'Ippon BCP600', '491', 'Кривоносов'),
    ('ИБП', 'Ippon BCP600', '492', 'Кичигина'),
    ('ИБП', 'Ippon BCP600', '487', 'Кравченко'),
    ('ИБП', 'Ippon BCP600', '495', 'Быстрицкий'),
    ('ИБП', 'Ippon BCP600', '494', None),
    ('ИБП', 'Ippon BCP600', '496', 'Баканов'),
    ('IP-телефон', 'Yealink SIP T46U', '00-000912', 'Дудоладов'),
    ('IP-телефон', 'Yealink SIP T46U', '00-000913', None),
    ('IP-телефон', 'Yealink SIP T46U', '00-000914', None),
    ('IP-телефон', 'Yealink SIP T46U', '00-000915', 'Ковалев'),
    ('IP-телефон', 'Yealink SIP-T31P', '00-000994', 'Костенко'),
    ('IP-телефон', 'Yealink SIP-T31P', '00-000996', 'Долгов'),
    ('IP-телефон', 'Yealink SIP-T31P', '00-000995', None),
    ('IP-телефон', 'Yealink SIP-T31P', '00-000997', 'Кривоносов'),
    ('IP-телефон', 'Yealink W52H', '00-000920', 'Попова'),
    ('IP-телефон', 'Yealink W52H', '00-000921', 'Попандопуло'),
    ('IP-телефон', 'Yealink W52H', '00-000922', 'Андреев'),
    ('IP-телефон', 'Yealink W52H', '00-000923', 'Бурнашкин'),
    ('IP-телефон', 'Yealink W52H', '00-000924', 'Потапов'),
    ('IP-телефон', 'Yealink W52H', '00-000925', 'Агамалян'),
    ('IP-телефон', 'Yealink W52H', '00-000945', 'Волк'),
    ('IP-телефон', 'Yealink W52P', '00-00008661', 'Долгов'),
    ('Ноутбук', 'Ноутбук DELL Vostro 3401', '00-000990', 'Попандопуло'),
    ('Ноутбук', 'Apple Macbook Pro 13 MR9Q2RU/A', None, 'Горобец'),
    ('Ноутбук', 'Ноутбук (без модели)', None, 'Долгов'),
    ('Монитор', 'Монитор AOC 24B2', '00-001001', 'Попандопуло'),
    ('Монитор', 'Монитор AOC 24B2', None, 'Долгов'),
    ('Сетевое оборудование', 'DLink DES-1024A', None, 'Негода'),
    ('Сетевое оборудование', 'DLink DGS-1005D', None, 'Негода'),
    ('Прочее', 'Вебкамера Logitech', None, 'Толкунов'),
    ('Прочее', 'Колонки Genius', '162', 'Бурнашкин'),
    ('Прочее', 'Колонки Genius', '186', 'Белова'),
    ('Прочее', 'Колонки Genius', '160', 'Колесникова'),
    ('Прочее', 'Колонки Genius', '39', 'Волк'),
    ('Прочее', 'Колонки Sven', None, 'Дудоладов'),
    ('Прочее', 'Колонки Sven 230', None, 'Веренич'),
    ('ПК', 'Компьютер (системный блок)', '98', 'Дудоладов'),
    ('Аналоговый телефон', 'Panasonic KX2362', 'Т12', 'Белова'),
    ('Аналоговый телефон', 'Panasonic KX2362', 'Т15', 'Маслий'),
    ('Аналоговый телефон', 'Panasonic KX2362', 'T2', 'Веренич'),
    ('Аналоговый телефон', 'Panasonic KX2362', 'Т21', None),
    ('Аналоговый телефон', 'Panasonic KX2362', 'Т16', 'Ловкова'),
    ('Аналоговый телефон', 'Panasonic KX2365', 'Т6', 'Базалий'),
    ('Аналоговый телефон', 'Panasonic KX2365', '244', 'Быстрицкий'),
    ('Аналоговый телефон', 'Panasonic KX-TG6711RU', 'т10', 'Колесникова'),
    ('Аналоговый телефон', 'Panasonic KX-TS2388RU', '8471', 'Гаспарян'),
]

assets = requests.get(f'{BASE}/api/assets', headers=H, timeout=10).json()
done = 0
missing = []
for atype, model, inv, resp in ASSIGN:
    if resp is None:
        continue
    emp_id = ids.get(resp)
    if not emp_id:
        missing.append(resp)
        continue
    candidates = [a for a in assets
                  if a['asset_type'] == atype and a['model'] == model
                  and (a['inventory_number'] or '') == (inv or '')]
    for a in candidates[:1]:
        requests.post(f'{BASE}/api/assets/{a["id"]}/assign/{emp_id}', headers=H, timeout=10)
        done += 1

print('assigned:', done, 'missing employees:', set(missing) if missing else 'none')
