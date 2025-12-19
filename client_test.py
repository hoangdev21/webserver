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
import argparse
import random
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from datetime import datetime

# ============================================================================
# HTTP CLIENT
# ============================================================================

class HTTPClient:
    """Client để test HTTP Server"""
    
    def __init__(self, host='locahost', port=8000, timeout=10, inject_failure_rate=0.0):
        """Khởi tạo client

        Args:
            host: server host
            port: server port
            timeout: socket timeout (seconds)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.inject_failure_rate = max(0.0, min(1.0, float(inject_failure_rate)))
        self.results = []
        self._lock = threading.Lock()
    
    def gui_request(self, path='/', method='GET', request_id=0):
        """Gửi HTTP request và nhận response
        Error code (500/503/504)
        """
        start_time = time.time()
        result = {'request_id': request_id, 'path': path, 'method': method,
                  'status_code': None, 'response_time': None, 'content_length': 0,
                  'error': None, 'success': False, 'simulated': False}

        # Optionally inject simulated failure
        if self.inject_failure_rate and random.random() < self.inject_failure_rate:
            result['simulated'] = True
            # choose between raising a network-level error or returning a server error code
            if random.random() < 0.4:
                # network error
                time.sleep(random.uniform(0.01, 0.1))
                result['error'] = 'SimulatedNetworkError'
                result['response_time'] = (time.time() - start_time) * 1000
                with self._lock:
                    self.results.append(result)
                return result
            else:
                # server error code
                chosen = random.choice([500, 503, 504])
                result['status_code'] = chosen
                result['error'] = f'SimulatedHTTP{chosen}'
                result['success'] = False
                result['response_time'] = (time.time() - start_time) * 1000
                with self._lock:
                    self.results.append(result)
                return result

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))

            req = f'{method} {path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\nConnection: close\r\n\r\n'
            sock.sendall(req.encode('utf-8'))

            resp_data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp_data += chunk
            sock.close()

            if resp_data:
                resp_str = resp_data.decode('utf-8', errors='ignore')
                lines = resp_str.split('\r\n')
                if lines:
                    parts = lines[0].split(' ')
                    if len(parts) >= 2:
                        try:
                            result['status_code'] = int(parts[1])
                        except:
                            result['status_code'] = None
                        result['success'] = True if (result['status_code'] and 200 <= result['status_code'] < 400) else False
                    for line in lines[1:]:
                        if line.lower().startswith('content-length:'):
                            try:
                                result['content_length'] = int(line.split(':', 1)[1].strip())
                            except:
                                pass
                            break

        except socket.timeout:
            result['error'] = 'Timeout'
        except ConnectionRefusedError:
            result['error'] = 'Kết nối từ chối'
        except Exception as e:
            result['error'] = str(e)
        finally:
            # always set response time
            result['response_time'] = (time.time() - start_time) * 1000

        with self._lock:
            self.results.append(result)
        return result
    
    def test_concurrent(self, num_requests=20, paths=None, concurrency=5, method='GET', write_json=False, send_api=False):
        """Test gửi nhiều requests đồng thời, song song
        """
        if paths is None:
            paths = ['/', '/about.html', '/style.css']
        self.results = []
        print('=' * 70)
        print(f'TEST THREADING - Gửi {num_requests} requests (concurrency={concurrency})')
        print('=' * 70 + '\n')

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(self.gui_request, paths[i % len(paths)], method, i + 1)
                       for i in range(num_requests)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f'Lỗi: {e}')

        total_time = time.time() - start_time
        self.hien_thi_ket_qua(total_time)

        if write_json:
            self.write_results_json(total_time)

        if send_api:
            self.gui_ket_qua_api()
    
    def hien_thi_ket_qua(self, total_time):
        """Hiển thị kết quả test"""
        if not self.results:
            print('Không có kết quả')
            return

        total_requests = len(self.results)
        success = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]

        print('KẾT QUẢ CHI TIẾT:')
        print('-' * 70)
        print(f'{"ID":<5} {"Path":<20} {"Method":<8} {"Status":<8} {"Time(ms)":<10}')
        print('-' * 70)

        for r in sorted(self.results, key=lambda x: x['request_id']):
            status = str(r['status_code']) if r.get('status_code') else ('ERR' if r.get('error') else '')
            err = f" ({r['error']})" if r.get('error') else ""
            sim = ' [sim]' if r.get('simulated') else ''
            print(f"{r['request_id']:<5} {r['path']:<20} {r['method']:<8} {status:<8} {r['response_time']:<10.2f}{sim}{err}")

        print('-' * 70 + '\n')
        print('THỐNG KÊ:')
        print('-' * 70)
        print(f'Tổng: {total_requests} | Thành công: {len(success)} | Thất bại: {len(failed)}')
        print(f'Tỷ lệ: {len(success) / total_requests * 100:.1f}%')
        print()

        times = [r['response_time'] for r in self.results if r.get('response_time') is not None]
        if times:
            print(f'Thời gian: Min={min(times):.2f}ms | Max={max(times):.2f}ms | Avg={statistics.mean(times):.2f}ms')
        sizes = [r.get('content_length', 0) for r in self.results if r.get('content_length') is not None]
        if sizes:
            print(f'Dữ liệu: Tổng={sum(sizes)} bytes | Avg={statistics.mean(sizes):.0f} bytes')
        print(f'Throughput: {total_requests / total_time:.2f} req/s')
        print()

        codes = {}
        for r in self.results:
            code = r.get('status_code') if r.get('status_code') is not None else (r.get('error') or 'ERROR')
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
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(req.encode('utf-8') + json_bytes)

            resp = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
            sock.close()

            if '200 OK' in resp.decode('utf-8', errors='ignore'):
                print('✓ Gửi kết quả thành công')
            else:
                print('✗ Gửi kết quả thất bại')
        except Exception as e:
            print(f'✗ Lỗi API: {e}')

    def write_results_json(self, total_time, out_path=None):
        """Write results summary + details to a JSON file (default: public/last_results.json)"""
        try:
            if out_path is None:
                out_dir = os.path.join(os.path.dirname(__file__), 'public')
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, 'last_results.json')

            data = {
                'timestamp': datetime.now().isoformat(),
                'total_requests': len(self.results),
                'total_time_s': round(total_time, 3),
                'throughput_rps': round(len(self.results) / total_time, 3) if total_time > 0 else None,
                'results': self.results
            }
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f'✓ Wrote results JSON to {out_path}')
        except Exception as e:
            print(f'✗ Lỗi khi ghi JSON: {e}')


# MAIN

def main():
    """Chạy test (CLI) - compatible với cấu hình từ web client

    Các tuỳ chọn CLI:
      --host HOST
      --port PORT
      --num-requests N
    """
    parser = argparse.ArgumentParser(description='Client test runner')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', default=5000, type=int)
    parser.add_argument('--num-requests', default=20, type=int)
    parser.add_argument('--concurrency', default=5, type=int)
    parser.add_argument('--timeout', default=10, type=float)
    parser.add_argument('--paths', default='/', help='Comma-separated paths')
    parser.add_argument('--method', default='GET', choices=['GET', 'HEAD'])
    parser.add_argument('--inject-failure-rate', default=0.0, type=float, help='Probability to inject simulated failure (0..1)')
    parser.add_argument('--write-json', action='store_true', help='Write results to public/last_results.json')
    parser.add_argument('--send-api', action='store_true', help='POST results to /api/test-results')
    args = parser.parse_args()

    HOST, PORT = args.host, args.port
    NUM_REQUESTS = args.num_requests 
    concurrency = args.concurrency
    timeout = args.timeout
    paths = [p.strip() for p in args.paths.split(',') if p.strip()]
    method = args.method
    inject_rate = args.inject_failure_rate
    write_json = args.write_json
    send_api = args.send_api


    

    client = HTTPClient(HOST, PORT, timeout=timeout, inject_failure_rate=inject_rate)

    print('Kiểm tra kết nối server...')
    try:
        result = client.gui_request('/', method, 0)
        if result['success'] or (result.get('status_code') in (200, 301, 302)):
            print(f'✓ Server online tại http://{HOST}:{PORT}\n')
        else:
            print(f'✗ Server lỗi: {result.get("error") or result.get("status_code")}\nChạy: python server.py')
            return
    except Exception as e:
        print(f'✗ Lỗi: {e}')
        return

    client.test_concurrent(NUM_REQUESTS, paths, concurrency=concurrency, method=method, write_json=write_json, send_api=send_api)

    if paths:
        print('\nTEST PATHS RIÊNG:')
        print('-' * 70)
        client.results = []
        for i, path in enumerate(paths, start=1):
            client.gui_request(path, method, i)

        for r in client.results:
            status = 'OK' if r['success'] else 'FAIL'
            print(f'{status}: {r["path"]} - Status: {r.get("status_code") or "ERR"} - Time: {r["response_time"]:.2f}ms')

    print('\nHoàn thành!')


if __name__ == '__main__':
    main()
