from tools.ssh_tool import PersistentSSHSession
import os

# Quick test: specify HOST via env or change below
HOST = os.getenv('TEST_HOST', '192.168.1.23')
USER = os.getenv('SSH_USER', 'jdd')
PASSWORD = os.getenv('SSH_PASSWORD', 5211)

try:
    s = PersistentSSHSession(host=HOST, user=USER, password=PASSWORD)
    print('WHOAMI:', s.send_command('whoami'))
    print('LS /:', s.send_command('ls -la /'))
    s.close()
except Exception as e:
    print('SSH test failed:', e)
