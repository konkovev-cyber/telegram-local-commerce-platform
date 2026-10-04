# -*- coding: utf-8 -*-
import requests

BASE = 'http://192.168.100.222:9000'
r = requests.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin'}, timeout=10)
H = {'Authorization': 'Bearer ' + r.json()['access_token'], 'Content-Type': 'application/json'}

EMPS = [
    ('Голяев Сергей Александрович', 'gkboss1', 'Руководство'),
    ('Завгородний Константин Владимирович', 'gkboss', 'Руководство'),
    ('Борисова Ирина Александровна', 'gkbuh', 'Бухгалтерия'),
    ('Степанова Дарья Валерьевна', 'gkab11', 'Бухгалтерия'),
    ('Устинова Татьяна Валерьевна', 'gkab11', 'Бухгалтерия'),
    ('Киркорова Елена Владимировна', 'gkab8', 'Бухгалтерия'),
    ('Ченцова Светлана Викторовна', 'gkur2', 'Юристы'),
    ('Жбырь Ирина Федоровна', 'gkur3', 'Юристы'),
    ('Калустова Анастасия Николаевна', 'gkur5', 'Юристы'),
    ('Фисун Людмила Ивановна', 'gkur4', 'Юристы'),
    ('Шпакова Юлия Юрьевна', 'gkurist', 'Кадры'),
    ('Кононова Лидия Александровна', 'gkpriem2', 'Приемная'),
    ('Васюкова Валентина Васильевна', 'gkkas', 'Касса'),
    ('Крапивка Олеся Юрьевна', 'gktr1', 'Диспетчер'),
    ('Шеремет Анастасия Александровна', 'gktr1', 'Диспетчер'),
    ('Помелило Денис Викторович', 'gktr5', 'Механик'),
    ('Школьный Виталий Леонидович', 'gktr3', 'Механик'),
    ('Томилов Сергей Валентинович', 'gktr13', 'Гл. механик'),
    ('Шадже Руслан Кимович', 'gknachtr', 'Нач. трансп. отдела'),
    ('Пономаренко Александр Сергеевич', 'gklg2', 'Логист'),
    ('Терехина Маргарита Викторовна', 'gklg3', 'Логист'),
    ('Мишенина Марина Александровна', 'gklogist5', 'Логист'),
    ('Пашкевич Елена Семеновна', 'gklogist5', 'Логист'),
    ('Белоусова Анастасия Александровна', 'gklogist5', 'Логист'),
    ('Чечиль Алина Константиновна', 'gklog777', 'Логист'),
    ('Шадже Милана Руслановна', 'gklog12', 'Логист'),
    ('Емельяненко Наталья Анатольевна', 'gkabon12', 'Абон. отдел'),
    ('Николаева Анна Ивановна', 'gkabon3', 'Абон. отдел'),
    ('Богомазова Олеся Анатольевна', 'gkab7', 'Абон. отдел'),
    ('Кошелева Юлия Юрьевна', 'gkab2', 'Абон. отдел'),
    ('Данилюк Татьяна Валериевна', 'gkab9', 'Абон. отдел'),
    ('Харькова Мария Юрьевна', 'gkab13', 'Абон. отдел'),
]

existing = {e['full_name']: e['id'] for e in requests.get(f'{BASE}/api/employees', headers=H, timeout=10).json()}
created = 0
ids = {}
for full, login, dept in EMPS:
    if full in existing:
        ids[full.split()[0]] = existing[full]
        continue
    resp = requests.post(f'{BASE}/api/employees', headers=H, timeout=10,
                         json={'full_name': full, 'domain_login': login,
                               'department': 'Горячий Ключ', 'position': dept})
    if resp.status_code == 201:
        ids[full.split()[0]] = resp.json()['id']
        created += 1

with open(r'D:\!AiSite\sysadmin\sysvault\emp_ids.json', 'w', encoding='utf-8') as f:
    import json
    json.dump(ids, f, ensure_ascii=False)
print('created:', created, 'total known:', len(ids))
