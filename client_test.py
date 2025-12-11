#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Client cho Web Server
Gửi nhiều requests đồng thời để test threading
"""

import socket
import threading
import time
import statistics
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from datetime import datetime

# ============================================================================
# HTTP CLIENT
# ============================================================================

class HTTPClient:
    """Client để test HTTP Server"""
    
    def __init__(self, host='127.0.0.1', port=8000):
        """Khởi tạo client"""
        self.host = host
        self.port = port
        self.results = []
        self._lock = threading.Lock()
    
    def gui_request(self, path='/', method='GET', request_id=0):
        """Gửi HTTP request và nhận response"""
        start_time = time.time()
        result = {'request_id': request_id, 'path': path, 'method': method, 
                 'status_code': None, 'response_time': None, 'content_length': 0,
                 'error': None, 'success': False}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            
            req = f'{method} {path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\nConnection: close\r\n\r\n'
            sock.sendall(req.encode('utf-8'))
            
            resp_data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk: break
                resp_data += chunk
            sock.close()
            
            if resp_data:
                resp_str = resp_data.decode('utf-8', errors='ignore')
                lines = resp_str.split('\r\n')
                if lines:
                    parts = lines[0].split(' ')
                    if len(parts) >= 2:
                        result['status_code'] = int(parts[1])
                        result['success'] = True
                    for line in lines[1:]:
                        if line.lower().startswith('content-length:'):
                            try:
                                result['content_length'] = int(line.split(':')[1].strip())
                            except: pass
                            break
        
        except socket.timeout:
            result['error'] = 'Timeout'
        except ConnectionRefusedError:
            result['error'] = 'Kết nối từ chối'
        except Exception as e:
            result['error'] = str(e)
        finally:
            result['response_time'] = (time.time() - start_time) * 1000
        
        with self._lock:
            self.results.append(result)
        return result
    
    def test_concurrent(self, num_requests=20, paths=None):
        """Test gửi nhiều requests đồng thời"""
        if paths is None:
            paths = ['/', '/about.html', '/style.css']
        
        self.results = []
        print('=' * 70)
        print(f'TEST THREADING - Gửi {num_requests} requests đồng thời')
        print('=' * 70 + '\n')
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.gui_request, paths[i % len(paths)], 'GET', i + 1) 
                      for i in range(num_requests)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f'Lỗi: {e}')
        
        self.hien_thi_ket_qua(time.time() - start_time)
        self.gui_ket_qua_api()
    
    def hien_thi_ket_qua(self, total_time):
        """Hiển thị kết quả test"""
        if not self.results:
            print('Không có kết quả')
            return
        
        success = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        
        print('KẾT QUẢ CHI TIẾT:')
        print('-' * 70)
        print(f'{"ID":<5} {"Path":<20} {"Method":<8} {"Status":<8} {"Time(ms)":<10}')
        print('-' * 70)
        
        for r in sorted(self.results, key=lambda x: x['request_id']):
            status = str(r['status_code']) if r['status_code'] else 'ERROR'
            err = f" ({r['error']})" if r['error'] else ""
            print(f"{r['request_id']:<5} {r['path']:<20} {r['method']:<8} {status:<8} {r['response_time']:<10.2f}{err}")
        
        print('-' * 70 + '\n')
        print('THỐNG KÊ:')
        print('-' * 70)
        print(f'Tổng: {len(self.results)} | Thành công: {len(success)} | Thất bại: {len(failed)}')
        print(f'Tỷ lệ: {len(success) / len(self.results) * 100:.1f}%')
        print()
        
        if success:
            times = [r['response_time'] for r in success]
            sizes = [r['content_length'] for r in success]
            print(f'Thời gian: Min={min(times):.2f}ms | Max={max(times):.2f}ms | Avg={statistics.mean(times):.2f}ms')
            print(f'Dữ liệu: Tổng={sum(sizes)} bytes | Avg={statistics.mean(sizes):.0f} bytes')
            print(f'Throughput: {len(success) / total_time:.2f} req/s')
            print()
            
            codes = {}
            for r in success:
                code = r['status_code']
                codes[code] = codes.get(code, 0) + 1
            print('Status codes:', codes)
        
        print('=' * 70)
    
    def gui_ket_qua_api(self):
        """Gửi kết quả test lên server qua API"""
        try:
            data = {'timestamp': datetime.now().isoformat(), 'total_requests': len(self.results), 'results': self.results}
            json_bytes = json.dumps(data).encode('utf-8')
            
            req = (f'POST /api/test-results HTTP/1.1\r\n'
                   f'Host: {self.host}:{self.port}\r\n'
                   f'Content-Type: application/json\r\n'
                   f'Content-Length: {len(json_bytes)}\r\n'
                   f'Connection: close\r\n\r\n')
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            sock.sendall(req.encode('utf-8') + json_bytes)
            
            resp = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk: break
                resp += chunk
            sock.close()
            
            if '200 OK' in resp.decode('utf-8', errors='ignore'):
                print('✓ Gửi kết quả thành công')
            else:
                print('✗ Gửi kết quả thất bại')
        except Exception as e:
            print(f'✗ Lỗi API: {e}')


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Chạy test"""
    HOST, PORT, NUM_REQUESTS = '127.0.0.1', 5000, 20
    paths = ['/', '/index.html', '/about.html', '/style.css', '/404.html', '/notfound.html']
    
    client = HTTPClient(HOST, PORT)
    
    print('Kiểm tra kết nối server...')
    try:
        result = client.gui_request('/', 'GET', 0)
        if result['success']:
            print(f'✓ Server online tại http://{HOST}:{PORT}\n')
        else:
            print(f'✗ Server lỗi: {result["error"]}\nChạy: python server.py')
            return
    except Exception as e:
        print(f'✗ Lỗi: {e}')
        return
    
    client.test_concurrent(NUM_REQUESTS, paths)
    
    print('\nTEST PATHS RIÊNG:')
    print('-' * 70)
    client.results = []
    for path in paths:
        client.gui_request(path, 'GET', 0)
    
    for r in client.results:
        status = 'OK' if r['success'] else 'FAIL'
        print(f'{status}: {r["path"]} - Status: {r["status_code"] or "ERR"} - Time: {r["response_time"]:.2f}ms')
    
    print('\nHoàn thành!')


if __name__ == '__main__':
    main()
