#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Server Tĩnh hỗ trợ đa luồng (Threading)
Sử dụng ThreadPoolExecutor để xử lý nhiều client đồng thời
"""

import socket
import logging
import logging.handlers
import json
import os
import mimetypes
import signal
import sys
import threading
import random
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ============================================================================
# CẤU HÌNH LOGGING THREAD-SAFE
# ============================================================================

class ThreadSafeLogger:
    """Logger thread-safe cho web server"""
    
    def __init__(self, log_file):
        """
        Khởi tạo logger thread-safe
        
        Args:
            log_file (str): Đường dẫn đến file log
        """
        # Tạo thư mục logs nếu chưa tồn tại
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Cấu hình logger
        self.logger = logging.getLogger('HTTPServer')
        self.logger.setLevel(logging.DEBUG)
        
        # Handler cho file
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        # Handler cho console
        console_handler = logging.StreamHandler()
        
        # Format log
        formatter = logging.Formatter(
            '%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self._lock = threading.Lock()
        
        # Lưu trữ logs (tối đa 500 dòng)
        self.log_buffer = []
        self.max_logs = 500
        
        # Thêm thông báo khởi tạo
        init_msg = self.tao_log_entry('INFO', 'Logger khởi tạo')
        self.log_buffer.append(init_msg)
    
    def them_vao_bo_dem(self, msg):
        """Thêm log vào bộ đệm"""
        if len(self.log_buffer) >= self.max_logs:
            self.log_buffer.pop(0)
        self.log_buffer.append(msg)
    
    def tao_log_entry(self, level, msg):
        """Tạo log entry với format đầy đủ"""
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f'{ts} - [{threading.current_thread().name}] - {level} - {msg}'
    
    def info(self, msg):
        """Log thông tin"""
        with self._lock:
            self.logger.info(msg)
            self.them_vao_bo_dem(self.tao_log_entry('INFO', msg))
    
    def error(self, msg):
        """Log lỗi"""
        with self._lock:
            self.logger.error(msg)
            self.them_vao_bo_dem(self.tao_log_entry('ERROR', msg))
    
    def warning(self, msg):
        """Log cảnh báo"""
        with self._lock:
            self.logger.warning(msg)
            self.them_vao_bo_dem(self.tao_log_entry('WARNING', msg))
    
    def debug(self, msg):
        """Log gỡ lỗi"""
        with self._lock:
            self.logger.debug(msg)
            self.them_vao_bo_dem(self.tao_log_entry('DEBUG', msg))


# ============================================================================
# HTTP SERVER CLASS
# ============================================================================

class HTTPServer:
    """
    Web Server tĩnh hỗ trợ đa luồng
    
    Features:
    - Xử lý HTTP GET và HEAD
    - Phục vụ file tĩnh từ thư mục public/
    - MIME type detection
    - Path traversal protection
    - Graceful shutdown
    - Thread-safe logging
    """
    
    # HTTP status codes và messages
    STATUS_CODES = {
        200: 'OK',
        304: 'Not Modified',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        500: 'Internal Server Error',
        501: 'Not Implemented',
    }
    
    # MIME types
    MIME_TYPES = {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.ico': 'image/x-icon',
        '.svg': 'image/svg+xml',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain; charset=utf-8',
    }
    
    def __init__(self, config_file='config.json'):
        """Khởi tạo HTTP Server"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.logger = ThreadSafeLogger(self.config['log_file'])
        self.host = self.config['host']
        self.port = self.config['port']
        self.max_threads = self.config['max_threads']
        self.public_dir = Path(self.config['public_dir']).resolve()
        self.chunk_size = self.config.get('chunk_size', 8192)
        self.timeout = self.config.get('timeout', 30)
        self.failure_rate = self.config.get('failure_rate', 0.0)
        self.enable_failure_simulation = self.config.get('enable_failure_simulation', False)
        
        self._running = True
        self._shutdown_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads, thread_name_prefix='HTTPWorker')
        self.server_socket = None
        self.test_results = []
        self._results_lock = threading.Lock()
        
        signal.signal(signal.SIGINT, self.xu_ly_tin_hieu)
        signal.signal(signal.SIGTERM, self.xu_ly_tin_hieu)
        
        self.logger.info(f'Web Server khởi tạo - {self.host}:{self.port}')
        self.logger.info(f'Public dir: {self.public_dir}')
        self.logger.info(f'Max threads: {self.max_threads}')
        log_msg = f'Failure simulation: {"ENABLED" if self.enable_failure_simulation else "DISABLED"}'
        if self.enable_failure_simulation:
            log_msg += f' - {self.failure_rate*100:.1f}%'
        self.logger.info(log_msg)
    
    def xu_ly_tin_hieu(self, signum, frame):
        """Xử lý tín hiệu shutdown"""
        self.logger.info('Nhận tín hiệu shutdown, đang dừng...')
        self._running = False
        self._shutdown_event.set()
    
    def start(self):
        """Khởi động server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)
            
            self.logger.info(f'Server bắt đầu tại http://{self.host}:{self.port}')
            self.logger.info('Nhấn Ctrl+C để dừng\n')
            
            while self._running:
                try:
                    sock, addr = self.server_socket.accept()
                    self.executor.submit(self.xu_ly_client, sock, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        self.logger.error(f'Lỗi accept: {e}')
        except OSError as e:
            self.logger.error(f'Lỗi socket: {e}')
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Dừng server"""
        self.logger.info('Đang dừng server...')
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        self.executor.shutdown(wait=True)
        self.logger.info('Server đã dừng')
    
    def can_that_bai(self):
        """Kiểm tra xem request có nên thất bại hay không"""
        return self.enable_failure_simulation and self.failure_rate > 0 and random.random() < self.failure_rate
    
    def loi_that_bai_ngau_nhien(self):
        """Trả về error status code ngẫu nhiên cho failure simulation"""
        return random.choice([
            (500, 'Internal Server Error', 'Lỗi server nội bộ (mô phỏng)'),
            (503, 'Service Unavailable', 'Dịch vụ tạm thời không khả dụng (mô phỏng)'),
            (504, 'Gateway Timeout', 'Kết nối server bị timeout (mô phỏng)'),
        ])
    
    def xu_ly_client(self, sock, addr):
        """Xử lý một client connection"""
        ip, port = addr
        try:
            sock.settimeout(self.timeout)
            
            # Nhận HTTP request
            req = b''
            while True:
                try:
                    data = sock.recv(1024)
                    if not data: break
                    req += data
                    if b'\r\n\r\n' in req: break
                except socket.timeout:
                    break
            
            if not req:
                self.logger.warning(f'{ip}:{port} - Không nhận được request')
                return
            
            # Parse HTTP request
            try:
                req_str = req.decode('utf-8', errors='ignore')
                lines = req_str.split('\r\n')
                if not lines: return
                
                parts = lines[0].split(' ')
                if len(parts) < 3:
                    self._gửi_phản_hồi(sock, 400, 'Bad Request', '')
                    return
                
                method, path, version = parts[0].upper(), parts[1], parts[2]
                self.logger.info(f'{ip}:{port} - {method} {path} {version}')
                
                # Mô phỏng failure
                if self.can_that_bai():
                    code, msg, err = self.loi_that_bai_ngau_nhien()
                    self.logger.warning(f'{ip}:{port} - {code}: {path} (Failure simulation)')
                    self.gui_phan_hoi(sock, code, msg, f'{err}\n')
                    return
                
                if method not in ['GET', 'HEAD', 'POST']:
                    self.gui_phan_hoi(sock, 405, 'Method Not Allowed', f'Phương thức {method} không được hỗ trợ\n')
                    return
                
                # Parse URL
                parsed = urlparse(path)
                file_path = unquote(parsed.path)

                # Accept trailing slash on file URLs (e.g., /client.html/) by stripping it
                if file_path != '/' and file_path.endswith('/'):
                    candidate = file_path.rstrip('/')
                    candidate_full = self.public_dir / candidate.lstrip('/')
                    if candidate_full.exists() and candidate_full.is_file():
                        self.logger.debug(f'Normalizing trailing slash for {file_path} -> {candidate}')
                        file_path = candidate
                
                # Xử lý API
                if file_path.startswith('/api/'):
                    self.xu_ly_api(sock, method, file_path, req, ip, port)
                    return
                
                # Ngăn path traversal
                if not self.khoa_yen_to(file_path):
                    self.logger.warning(f'{ip}:{port} - Path traversal: {file_path}')
                    self.gui_phan_hoi(sock, 403, 'Forbidden', 'Truy cập bị từ chối\n')
                    return
                
                # Xác định file
                file_path = '/index.html' if file_path == '/' else file_path
                full_path = self.public_dir / file_path.lstrip('/')
                
                if not full_path.exists():
                    self.logger.info(f'{ip}:{port} - 404: {file_path}')
                    err_file = self.public_dir / '404.html'
                    if err_file.exists():
                        with open(err_file, 'rb') as f:
                            self.gui_phan_hoi(sock, 404, 'Not Found', f.read(), is_binary=True)
                    else:
                        self.gui_phan_hoi(sock, 404, 'Not Found', 'File không tìm thấy\n')
                    return
                
                if not full_path.is_file():
                    self.gui_phan_hoi(sock, 403, 'Forbidden', 'Không phải là file\n')
                    return
                
                # Đọc và gửi file
                with open(full_path, 'rb') as f:
                    content = f.read()
                
                mime = self.xac_dinh_kieu_mime(str(full_path))
                header = f'HTTP/1.1 200 OK\r\nContent-Type: {mime}\r\nContent-Length: {len(content)}\r\nConnection: close\r\n\r\n'
                sock.sendall(header.encode('utf-8'))
                if method == 'GET':
                    sock.sendall(content)
                self.logger.info(f'{ip}:{port} - 200: {file_path} ({len(content)} bytes)')
            
            except Exception as e:
                self.logger.error(f'{ip}:{port} - Lỗi xử lý request: {e}')
                self.gui_phan_hoi(sock, 500, 'Internal Server Error', 'Lỗi server nội bộ\n')
        
        except Exception as e:
            self.logger.error(f'{ip}:{port} - Lỗi kết nối: {e}')
        
        finally:
            try:
                sock.close()
            except:
                pass
    
    def xu_ly_api(self, sock, method, path, req, ip, port):
        """Xử lý API requests"""
        try:
            if path == '/api/test-results' and method == 'POST':
                try:
                    req_str = req.decode('utf-8', errors='ignore')
                    body_start = req_str.find('\r\n\r\n') + 4
                    test_data = json.loads(req_str[body_start:])
                    
                    with self._results_lock:
                        self.test_results = test_data
                    
                    count = len(test_data.get('results', []))
                    self.logger.info(f'{ip}:{port} - POST /api/test-results - Lưu {count} kết quả')
                    
                    resp = json.dumps({'success': True, 'message': 'Đã lưu kết quả test', 'count': count})
                    header = f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(resp.encode("utf-8"))}\r\nConnection: close\r\n\r\n'
                    sock.sendall(header.encode('utf-8') + resp.encode('utf-8'))
                except json.JSONDecodeError:
                    self.gui_phan_hoi(sock, 400, 'Bad Request', 'Invalid JSON')
            
            elif path == '/api/test-results' and method == 'GET':
                with self._results_lock:
                    resp = json.dumps(self.test_results)
                header = f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(resp.encode("utf-8"))}\r\nConnection: close\r\n\r\n'
                sock.sendall(header.encode('utf-8') + resp.encode('utf-8'))
            
            elif path == '/api/logs' and method == 'GET':
                with self.logger._lock:
                    logs = list(self.logger.log_buffer)
                resp = json.dumps({'timestamp': datetime.now().isoformat(), 'logs': logs})
                header = f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(resp.encode("utf-8"))}\r\nConnection: close\r\n\r\n'
                sock.sendall(header.encode('utf-8') + resp.encode('utf-8'))
            else:
                self.gui_phan_hoi(sock, 404, 'Not Found', 'API endpoint không tồn tại\n')
        except Exception as e:
            self.logger.error(f'{ip}:{port} - Lỗi xử lý API: {e}')
            self.gui_phan_hoi(sock, 500, 'Internal Server Error', 'Lỗi server nội bộ\n')
    
    def khoa_yen_to(self, file_path):
        """Kiểm tra path có an toàn (không bị path traversal attack)"""
        try:
            file_path = file_path.lstrip('/')
            if '..' in file_path or file_path.startswith('/'):
                return False
            full_path = (self.public_dir / file_path).resolve()
            full_path.relative_to(self.public_dir.resolve())
            return True
        except (ValueError, RuntimeError):
            return False
    
    def xac_dinh_kieu_mime(self, file_path):
        """Xác định MIME type của file"""
        ext = Path(file_path).suffix.lower()
        return self.MIME_TYPES.get(ext) or mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    
    def gui_phan_hoi(self, sock, code, msg, content, is_binary=False):
        """Gửi HTTP response"""
        try:
            header = f'HTTP/1.1 {code} {msg}\r\nContent-Type: text/html; charset=utf-8\r\n'
            content_bytes = content if is_binary else (content.encode('utf-8') if isinstance(content, str) else content)
            header += f'Content-Length: {len(content_bytes)}\r\nConnection: close\r\n\r\n'
            sock.sendall(header.encode('utf-8') + content_bytes)
        except Exception as e:
            self.logger.error(f'Lỗi gửi phản hồi: {e}')


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Điểm vào chính"""
    try:
        server = HTTPServer('config.json')
        server.start()
    except FileNotFoundError:
        print('Lỗi: Không tìm thấy file config.json')
        sys.exit(1)
    except Exception as e:
        print(f'Lỗi: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
