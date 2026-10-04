import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)

docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
project = '/volume1/docker/sysvault'

# Check images
cmd = f'{sudo} {docker} images 2>&1'
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print('IMAGES:', stdout.read().decode() + stderr.read().decode())

# Tag new image as sysadmin-backend
cmd = f'{sudo} {docker} tag sysvault-backend sysadmin-backend:latest 2>&1'
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print('TAG:', stdout.read().decode() + stderr.read().decode())

# Remove old containers
cmd = f'{sudo} {docker} rm -f sysadmin-backend-1 sysadmin-frontend-1 2>&1'
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print('RM:', stdout.read().decode() + stderr.read().decode())

client.close()
print('prep done')
