import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.100.222', port=2191, username='boss', password='Kk1478963', timeout=15)

docker = '/var/packages/ContainerManager/target/usr/bin/docker'
sudo = 'echo Kk1478963 | sudo -S'
project = '/volume1/docker/sysvault'

# Install fixed bcrypt in container
cmd = f'{sudo} {docker} exec sysvault-backend-1 pip install bcrypt==4.0.1 --quiet 2>&1'
stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
print('PIP INSTALL:', stdout.read().decode()[-500:] or stderr.read().decode()[-500:])

# Create admin user using bcrypt directly
create_user_cmd = f'''{sudo} {docker} exec sysvault-backend-1 python -c "
import asyncio, bcrypt
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

async def create_user():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            hashed = bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode()
            user = User(username='admin', hashed_password=hashed)
            db.add(user)
            await db.commit()
            print('Created admin user')
        else:
            print('Admin user exists')

asyncio.run(create_user())
"'''
stdin, stdout, stderr = client.exec_command(create_user_cmd, timeout=15)
print('USER:', stdout.read().decode() or stderr.read().decode())

# Restart backend to pick up bcrypt fix
cmd = f'{sudo} {docker} restart sysvault-backend-1'
stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
print('RESTART:', stdout.read().decode() or stderr.read().decode())

time.sleep(10)

# Check status
cmd = f'{sudo} {docker} ps --filter name=sysvault'
stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
print('STATUS:', stdout.read().decode() or stderr.read().decode())

client.close()
print('done')
