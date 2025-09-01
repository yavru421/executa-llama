import requests
import json

URL = 'http://127.0.0.1:8000/course-check'
SAMPLE = "User: show me disk usage\nAgent: suggested 'df -h'\nUser: run it"

resp = requests.post(URL, json={'conversation': SAMPLE})
print('status', resp.status_code)
try:
    data = resp.json()
    print('response keys:', list(data.keys()))
    if data.get('plan'):
        print('Parsed plan (len):', len(data['plan']))
        for i, step in enumerate(data['plan'], 1):
            print(i, step.get('prompt'), '->', step.get('action'))
    else:
        print('Error or unparsable:', data.get('error'))
        print('Raw output:', data.get('raw'))
except Exception as e:
    print('Failed to parse JSON:', e)
    print(resp.text)
