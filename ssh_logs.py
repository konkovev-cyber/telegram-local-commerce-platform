import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)
docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
cmd = f'{sudo} {docker} logs sysvault-backend 2>&1 | tail -30'
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
out = (stdout.read() + stderr.read()).decode('utf-8', errors='replace')
with open(r'D:\!AiSite\sysadmin\sysvault\be_logs.txt', 'w', encoding='utf-8') as f:
    f.write(out)
print('saved', len(out))
client.close()
