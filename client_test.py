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
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

# ============================================================================
# HTTP CLIENT
# ============================================================================

class HTTPClient:
    """Client để test HTTP Server"""
    
    def __init__(self, host='127.0.0.1', port=8000):
        """
        Khởi tạo client
        
        Args:
            host (str): Địa chỉ server
            port (int): Port server
        """
        self.host = host
        self.port = port
        self.base_url = f'http://{host}:{port}'
        
        # Lưu kết quả
        self.results = []
        self._lock = threading.Lock()
    
    def send_request(self, path='/', method='GET', request_id=0):
        """
        Gửi HTTP request và nhận response
        
        Args:
            path (str): Đường dẫn request
            method (str): HTTP method (GET, HEAD)
            request_id (int): ID của request (để tracking)
        
        Returns:
            dict: Thông tin response
        """
        start_time = time.time()
        result = {
            'request_id': request_id,
            'path': path,
            'method': method,
            'status_code': None,
            'response_time': None,
            'content_length': 0,
            'error': None,
            'success': False,
        }
        
        try:
            # Tạo socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            
            # Kết nối đến server
            sock.connect((self.host, self.port))
            
            # Gửi HTTP request
            request = f'{method} {path} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\nConnection: close\r\n\r\n'
            sock.sendall(request.encode('utf-8'))
            
            # Nhận response header
            response_data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            
            sock.close()
            
            # Parse response
            if response_data:
                response_str = response_data.decode('utf-8', errors='ignore')
                lines = response_str.split('\r\n')
                
                if lines:
                    # Parse status line
                    status_line = lines[0]
                    parts = status_line.split(' ')
                    if len(parts) >= 2:
                        result['status_code'] = int(parts[1])
                        result['success'] = True
                    
                    # Tìm Content-Length
                    for line in lines[1:]:
                        if line.lower().startswith('content-length:'):
                            try:
                                result['content_length'] = int(line.split(':')[1].strip())
                            except:
                                pass
                            break
            
        except socket.timeout:
            result['error'] = 'Timeout'
        except ConnectionRefusedError:
            result['error'] = 'Kết nối bị từ chối'
        except Exception as e:
            result['error'] = str(e)
        
        finally:
            result['response_time'] = (time.time() - start_time) * 1000  # milliseconds
        
        # Lưu result
        with self._lock:
            self.results.append(result)
        
        return result
    
    def test_concurrent(self, num_requests=20, paths=None):
        """
        Test gửi nhiều requests đồng thời
        
        Args:
            num_requests (int): Số requests
            paths (list): Danh sách paths để request
        """
        if paths is None:
            paths = ['/', '/about.html', '/style.css']
        
        self.results = []
        
        print('=' * 70)
        print(f'TEST THREADING - Gửi {num_requests} requests đồng thời')
        print('=' * 70)
        print()
        
        start_time = time.time()
        
        # Sử dụng ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10, thread_name_prefix='TestClient') as executor:
            futures = []
            
            for i in range(num_requests):
                path = paths[i % len(paths)]
                future = executor.submit(self.send_request, path, 'GET', i + 1)
                futures.append(future)
            
            # Đợi tất cả requests xong
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f'Lỗi: {e}')
        
        total_time = time.time() - start_time
        
        # Hiển thị kết quả
        self._print_results(total_time)
    
    def _print_results(self, total_time):
        """
        Hiển thị kết quả test
        
        Args:
            total_time (float): Tổng thời gian test
        """
        if not self.results:
            print('Không có kết quả')
            return
        
        # Phân loại kết quả
        success_results = [r for r in self.results if r['success']]
        failed_results = [r for r in self.results if not r['success']]
        
        print('KẾT QUẢ CHI TIẾT:')
        print('-' * 70)
        print(f'{"ID":<5} {"Path":<20} {"Method":<8} {"Status":<8} {"Time(ms)":<10} {"Size":<10}')
        print('-' * 70)
        
        for result in sorted(self.results, key=lambda x: x['request_id']):
            status = str(result['status_code']) if result['status_code'] else 'ERROR'
            error = f" ({result['error']})" if result['error'] else ""
            size = result['content_length']
            
            print(
                f"{result['request_id']:<5} "
                f"{result['path']:<20} "
                f"{result['method']:<8} "
                f"{status:<8} "
                f"{result['response_time']:<10.2f} "
                f"{size:<10}{error}"
            )
        
        print('-' * 70)
        print()
        
        # Thống kê
        print('THỐNG KÊ:')
        print('-' * 70)
        print(f'Tổng requests: {len(self.results)}')
        print(f'Thành công: {len(success_results)}')
        print(f'Thất bại: {len(failed_results)}')
        print(f'Tỷ lệ thành công: {len(success_results) / len(self.results) * 100:.1f}%')
        print()
        
        if success_results:
            response_times = [r['response_time'] for r in success_results]
            content_lengths = [r['content_length'] for r in success_results]
            
            print(f'Thời gian response:')
            print(f'  Min: {min(response_times):.2f} ms')
            print(f'  Max: {max(response_times):.2f} ms')
            print(f'  Avg: {statistics.mean(response_times):.2f} ms')
            print(f'  Median: {statistics.median(response_times):.2f} ms')
            print(f'  StdDev: {statistics.stdev(response_times):.2f} ms' if len(response_times) > 1 else '')
            print()
            
            total_size = sum(content_lengths)
            print(f'Kích thước dữ liệu:')
            print(f'  Tổng: {total_size} bytes')
            print(f'  Avg: {statistics.mean(content_lengths):.0f} bytes')
            print()
        
        print(f'Thời gian tổng cộng: {total_time:.2f} giây')
        print(f'Throughput: {len(success_results) / total_time:.2f} requests/giây')
        print()
        
        # Phân tích status code
        if success_results:
            status_codes = {}
            for r in success_results:
                code = r['status_code']
                status_codes[code] = status_codes.get(code, 0) + 1
            
            print('Phân bố Status Code:')
            for code in sorted(status_codes.keys()):
                count = status_codes[code]
                print(f'  {code}: {count}')
            print()
        
        print('=' * 70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Chạy test"""
    # Cấu hình test
    HOST = '127.0.0.1'
    PORT = 5000
    NUM_REQUESTS = 20
    
    # Các paths để test
    paths = [
        '/',
        '/index.html',
        '/about.html',
        '/style.css',
        '/404.html',
        '/notfound.html',  # Test 404
    ]
    
    # Tạo client
    client = HTTPClient(HOST, PORT)
    
    # Test 1: Kiểm tra server có online không
    print('Kiểm tra kết nối server...')
    try:
        result = client.send_request('/', 'GET', 0)
        if result['success']:
            print(f'✓ Server online tại http://{HOST}:{PORT}')
            print()
        else:
            print(f'✗ Server không phản hồi: {result["error"]}')
            print('Vui lòng chạy server trước: python server.py')
            return
    except Exception as e:
        print(f'✗ Lỗi kết nối: {e}')
        return
    
    # Test 2: Test threading
    client.test_concurrent(NUM_REQUESTS, paths)
    
    # Test 3: Test individual paths
    print('TEST CÁC PATHS RIÊNG LẺ:')
    print('-' * 70)
    
    client.results = []
    for path in paths:
        client.send_request(path, 'GET', 0)
    
    for result in client.results:
        status = 'OK' if result['success'] else 'FAIL'
        print(f'{status}: {result["path"]} - '
              f'Status: {result["status_code"] or "ERROR"} - '
              f'Time: {result["response_time"]:.2f}ms')
    
    print()
    print('Test hoàn thành!')


if __name__ == '__main__':
    main()
