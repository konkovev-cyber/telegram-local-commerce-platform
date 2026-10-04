import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)
docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
project = '/volume1/docker/sysvault'

files = [
    ('backend/app/models.py', '/app/app/models.py'),
    ('backend/app/main.py', '/app/app/main.py'),
    ('backend/app/services/inventory.py', '/app/app/services/inventory.py'),
    ('backend/app/api/inventory.py', '/app/app/api/inventory.py'),
]
for src, dst in files:
    cmd = f'{sudo} {docker} cp {project}/{src} sysvault-backend:{dst}'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print('cp', src)

cmd = f'{sudo} {docker} restart sysvault-backend'
stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
print('restarted')

time.sleep(8)

# Check new tables exist
check = "import sqlite3; c = sqlite3.connect('/data/database.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])"
cmd = f'{sudo} {docker} exec sysvault-backend python -c "{check}"'
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
out = stdout.read().decode() + stderr.read().decode()
print('TABLES:', out[:400])

# Test /api/meta endpoint
cmd = "curl -s http://127.0.0.1:9000/api/meta"
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print('META:', stdout.read().decode()[:200])

client.close()
print('backend deploy done')
