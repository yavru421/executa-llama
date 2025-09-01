import urllib.request, sys
url='http://127.0.0.1:8000/status'
try:
    with urllib.request.urlopen(url, timeout=3) as r:
        print('OK', r.status)
        print(r.read().decode('utf-8'))
except Exception as e:
    print('ERROR', e)
    sys.exit(1)
