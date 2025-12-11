#!/usr/bin/env python3
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 5000))
sock.sendall(b'GET /api/logs HTTP/1.1\r\nHost: 127.0.0.1:5000\r\nConnection: close\r\n\r\n')

data = b''
while True:
    chunk = sock.recv(4096)
    if not chunk: break
    data += chunk
sock.close()

resp_str = data.decode('utf-8', errors='ignore')
header_end = resp_str.find('\r\n\r\n')
if header_end != -1:
    body = resp_str[header_end+4:]
    try:
        result = json.loads(body)
        print(f'✓ Thành công! Lấy {len(result.get("logs", []))} logs')
        if result.get('logs'):
            print('Log mẫu:')
            for log in result['logs'][:5]:
                print(f'  {log}')
    except Exception as e:
        print(f'✗ Lỗi JSON: {e}')
        print(f'Preview: {body[:200]}')
