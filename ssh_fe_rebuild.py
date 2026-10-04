import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)
docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
project = '/volume1/docker/sysvault'

client.exec_command(f'{sudo} {docker} stop sysvault-frontend 2>/dev/null; {sudo} {docker} rm sysvault-frontend 2>/dev/null')
print('stopped')

cmd = f'{sudo} {docker} build --no-cache -t sysvault-frontend -f {project}/Dockerfile.frontend {project}'
stdin, stdout, stderr = client.exec_command(cmd, timeout=400)
out = stdout.read().decode()
err = stderr.read().decode()
ok = 'Successfully tagged' in out or 'Successfully built' in out
print('BUILD:', 'OK' if ok else 'FAIL')
if not ok:
    with open(r'D:\!AiSite\sysadmin\sysvault\fe_build_log.txt', 'w', encoding='utf-8', errors='replace') as f:
        f.write(out + '\n===ERR===\n' + err)
    for line in (out + err).split('\n'):
        if 'error' in line.lower():
            print(' ', line.strip()[:150])

if ok:
    client.exec_command(f'{sudo} {docker} run -d --name sysvault-frontend --network sysvault-net -p 9000:80 sysvault-frontend')
    time.sleep(5)
    stdin, stdout, stderr = client.exec_command('curl -s http://127.0.0.1:9000/api/health')
    print('HEALTH:', stdout.read().decode())
client.close()
print('done')
