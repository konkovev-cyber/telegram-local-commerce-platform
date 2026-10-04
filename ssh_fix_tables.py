import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)
docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'

# Drop old empty tables so create_all recreates with the new schema
sql = "import sqlite3; c = sqlite3.connect('/data/database.db'); c.execute('DROP TABLE IF EXISTS assets'); c.execute('DROP TABLE IF EXISTS employees'); c.commit(); print('dropped')"
cmd = f'{sudo} {docker} exec sysvault-backend python -c "{sql}"'
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print((stdout.read() + stderr.read()).decode().strip()[:200])

cmd = f'{sudo} {docker} restart sysvault-backend'
stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
print('restarted')
time.sleep(8)
client.close()
print('done')
