import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)
docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
project = '/volume1/docker/sysvault'

# Stop old
client.exec_command(f'{sudo} {docker} stop sysvault-frontend 2>/dev/null; {sudo} {docker} rm sysvault-frontend 2>/dev/null')
print('Stopped old frontend')

# Build
print('Building...')
cmd = f'{sudo} {docker} build --no-cache -t sysvault-frontend -f {project}/Dockerfile.frontend {project}'
stdin, stdout, stderr = client.exec_command(cmd, timeout=300)
out = stdout.read().decode()
err = stderr.read().decode()
ok = 'Successfully tagged' in out or 'Successfully built' in out
print('BUILD:', 'OK' if ok else 'FAIL')
if not ok:
    # Find the actual error
    for line in out.split('\n') + err.split('\n'):
        if 'error' in line.lower() and 'TS' in line:
            print('  TS ERROR:', line.strip())
            break
    print('Last 200 chars out:', out[-200:])
    print('Last 200 chars err:', err[-200:])

if ok:
    # Start
    cmd = f'{sudo} {docker} run -d --name sysvault-frontend --network sysvault-net -p 9000:80 sysvault-frontend'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print('Start:', stdout.read().decode().strip())
    time.sleep(5)
    # Check
    stdin, stdout, stderr = client.exec_command('curl -s http://127.0.0.1:9000/api/health')
    print('Health:', stdout.read().decode())
    stdin, stdout, stderr = client.exec_command('curl -s http://127.0.0.1:9000/ | head -3')
    html = stdout.read().decode()
    print('Has Ugolok:', 'Уголок' in html)

client.close()
print('done')
