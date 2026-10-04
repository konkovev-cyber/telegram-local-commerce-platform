import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)
sudo = 'echo Kk1478963 | sudo -S'

cmd = f'{sudo} rm -rf /volume1/docker/sysvault/frontend/node_modules && echo DELETED'
stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
print((stdout.read() + stderr.read()).decode()[:200])
client.close()
