import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)

docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
project = '/volume1/docker/sysvault'
secret = '7e41134137913d4e38cfb1c70bed1e687d5f40e8e3bda5275fd45af9d43b2974'

# Remove old
for name in ['sysvault-backend', 'sysvault-frontend']:
    client.exec_command(f'{sudo} {docker} rm -f {name} 2>/dev/null')

# Create network
client.exec_command(f'{sudo} {docker} network create sysvault-net 2>/dev/null')

# Start backend WITH network
cmd = f'{sudo} {docker} run -d --name sysvault-backend --network sysvault-net -v {project}/data:/data -e DATABASE_URL=sqlite+aiosqlite:////data/database.db -e SECRET_KEY={secret} -e DATA_DIR=/data -e ATTACHMENTS_DIR=/data/attachments -e BACKUPS_DIR=/data/backups -e SEED_DATA=false sysvault-backend uvicorn app.main:app --host 0.0.0.0 --port 8000'
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print('BACKEND:', stdout.read().decode().strip())

# Start frontend WITH network
cmd = f'{sudo} {docker} run -d --name sysvault-frontend --network sysvault-net -p 9000:80 sysvault-frontend'
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print('FRONTEND:', stdout.read().decode().strip())

time.sleep(5)

# Check
cmd = f'{sudo} {docker} ps'
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print('STATUS:', stdout.read().decode())

# Test from NAS
stdin, stdout, stderr = client.exec_command('curl -s http://127.0.0.1:9000/api/health', timeout=5)
print('HEALTH:', stdout.read().decode())

client.close()
print('done')
