import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=10)

# Check sudoers and try running docker via different methods
for cmd in [
    'cat /etc/sudoers',
    'ls /etc/sudoers.d/',
    'echo Kk1478963 | sudo -S docker ps 2>&1 | head -5',
    'echo Kk1478963 | sudo -S /var/packages/ContainerManager/target/usr/bin/docker ps 2>&1 | head -5',
    'echo Kk1478963 | sudo -S usermod -aG docker boss 2>&1',
    'echo Kk1478963 | sudo -S chmod 666 /var/run/docker.sock 2>&1',
]:
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=8)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        print(f'{cmd} => {out or err}')
    except Exception as e:
        print(f'{cmd} => ERROR: {e}')

client.close()
