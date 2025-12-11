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
        
        # Thêm thông báo khởi tạo vào buffer với format đầy đủ
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        thread_name = threading.current_thread().name
        init_msg = f'{timestamp} - [{thread_name}] - INFO - Logger initialized'
        self.log_buffer.append(init_msg)
    
    def _add_to_buffer(self, msg):
        """Thêm log vào buffer (gọi từ trong lock)"""
        self.log_buffer.append(msg)
        # Giữ tối đa max_logs dòng
        if len(self.log_buffer) > self.max_logs:
            self.log_buffer.pop(0)
    
    def info(self, msg):
        """Log info"""
        with self._lock:
            self.logger.info(msg)
            # Tạo log entry với format đầy đủ tương tự terminal
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            thread_name = threading.current_thread().name
            log_entry = f'{timestamp} - [{thread_name}] - INFO - {msg}'
            self._add_to_buffer(log_entry)
    
    def error(self, msg):
        """Log error"""
        with self._lock:
            self.logger.error(msg)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            thread_name = threading.current_thread().name
            log_entry = f'{timestamp} - [{thread_name}] - ERROR - {msg}'
            self._add_to_buffer(log_entry)
    
    def warning(self, msg):
        """Log warning"""
        with self._lock:
            self.logger.warning(msg)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            thread_name = threading.current_thread().name
            log_entry = f'{timestamp} - [{thread_name}] - WARNING - {msg}'
            self._add_to_buffer(log_entry)
    
    def debug(self, msg):
        """Log debug"""
        with self._lock:
            self.logger.debug(msg)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            thread_name = threading.current_thread().name
            log_entry = f'{timestamp} - [{thread_name}] - DEBUG - {msg}'
            self._add_to_buffer(log_entry)


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
        """
        Khởi tạo HTTP Server
        
        Args:
            config_file (str): Đường dẫn đến file cấu hình
        """
        # Load config
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # Khởi tạo logger
        self.logger = ThreadSafeLogger(self.config['log_file'])
        
        # Các thuộc tính server
        self.host = self.config['host']
        self.port = self.config['port']
        self.max_threads = self.config['max_threads']
        self.public_dir = Path(self.config['public_dir']).resolve()
        self.chunk_size = self.config.get('chunk_size', 8192)
        self.timeout = self.config.get('timeout', 30)
        
        # Flag kiểm soát shutdown
        self._running = True
        self._shutdown_event = threading.Event()
        
        # ThreadPoolExecutor để xử lý client
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_threads,
            thread_name_prefix='HTTPWorker'
        )
        
        # Socket server
        self.server_socket = None
        
        # Lưu trữ kết quả test
        self.test_results = []
        self._results_lock = threading.Lock()
        
        # Đăng ký signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f'Web Server khởi tạo - {self.host}:{self.port}')
        self.logger.info(f'Public dir: {self.public_dir}')
        self.logger.info(f'Max threads: {self.max_threads}')
    
    def _signal_handler(self, signum, frame):
        """
        Xử lý SIGINT và SIGTERM để graceful shutdown
        """
        self.logger.info('Nhận tín hiệu shutdown, đang dừng server...')
        self._running = False
        self._shutdown_event.set()
    
    def start(self):
        """
        Khởi động server
        """
        try:
            # Tạo server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            # Set timeout cho socket
            self.server_socket.settimeout(1)
            
            self.logger.info(f'Server bắt đầu lắng nghe tại http://{self.host}:{self.port}')
            self.logger.info('Nhấn Ctrl+C để dừng server\n')
            
            # Main loop
            while self._running:
                try:
                    # Accept kết nối từ client
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Submit task xử lý client vào thread pool
                    self.executor.submit(
                        self._handle_client,
                        client_socket,
                        client_address
                    )
                
                except socket.timeout:
                    # Timeout bình thường, kiểm tra shutdown event
                    continue
                except Exception as e:
                    if self._running:
                        self.logger.error(f'Lỗi accept: {e}')
        
        except OSError as e:
            self.logger.error(f'Lỗi socket: {e}')
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """
        Dừng server một cách an toàn (graceful shutdown)
        """
        self.logger.info('Đang dừng server...')
        
        # Đóng server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Đợi tất cả task xong
        self.executor.shutdown(wait=True)
        
        self.logger.info('Server đã dừng thành công')
    
    def _handle_client(self, client_socket, client_address):
        """
        Xử lý một client connection
        
        Args:
            client_socket: Socket của client
            client_address: Địa chỉ của client (host, port)
        """
        client_ip, client_port = client_address
        
        try:
            # Set timeout cho client socket
            client_socket.settimeout(self.timeout)
            
            # Nhận HTTP request
            request_data = b''
            while True:
                try:
                    chunk = client_socket.recv(1024)
                    if not chunk:
                        break
                    request_data += chunk
                    
                    # Kiểm tra nếu nhận được toàn bộ header (CRLF CRLF)
                    if b'\r\n\r\n' in request_data:
                        break
                
                except socket.timeout:
                    break
            
            if not request_data:
                self.logger.warning(f'{client_ip}:{client_port} - Không nhận được request')
                return
            
            # Parse HTTP request
            try:
                request_str = request_data.decode('utf-8', errors='ignore')
                lines = request_str.split('\r\n')
                
                if not lines:
                    return
                
                # Parse request line
                request_line = lines[0]
                parts = request_line.split(' ')
                
                if len(parts) < 3:
                    self._send_response(client_socket, 400, 'Bad Request', '')
                    return
                
                method = parts[0].upper()
                path = parts[1]
                http_version = parts[2]
                
                # Log request
                self.logger.info(f'{client_ip}:{client_port} - {method} {path} {http_version}')
                
                # Kiểm tra method
                if method not in ['GET', 'HEAD', 'POST']:
                    self._send_response(
                        client_socket,
                        405,
                        'Method Not Allowed',
                        f'Phương thức {method} không được hỗ trợ\n'
                    )
                    return
                
                # Parse URL
                parsed_url = urlparse(path)
                file_path = unquote(parsed_url.path)
                
                # Xử lý API requests
                if file_path.startswith('/api/'):
                    self._handle_api(client_socket, method, file_path, request_data, client_ip, client_port)
                    return
                
                # Ngăn chặn path traversal attack
                if not self._is_safe_path(file_path):
                    self.logger.warning(f'{client_ip}:{client_port} - Path traversal attempt: {file_path}')
                    self._send_response(client_socket, 403, 'Forbidden', 'Truy cập bị từ chối\n')
                    return
                
                # Xác định file cần serve
                if file_path == '/':
                    file_path = '/index.html'
                
                # Đọc file
                full_path = self.public_dir / file_path.lstrip('/')
                
                if not full_path.exists():
                    self.logger.info(f'{client_ip}:{client_port} - 404: {file_path}')
                    
                    # Đọc 404.html
                    error_page = self.public_dir / '404.html'
                    if error_page.exists():
                        with open(error_page, 'rb') as f:
                            content = f.read()
                        self._send_response(client_socket, 404, 'Not Found', content, is_binary=True)
                    else:
                        self._send_response(client_socket, 404, 'Not Found', 'File không tìm thấy\n')
                    return
                
                if not full_path.is_file():
                    self._send_response(client_socket, 403, 'Forbidden', 'Không phải là file\n')
                    return
                
                # Đọc và gửi file
                with open(full_path, 'rb') as f:
                    content = f.read()
                
                # Xác định MIME type
                mime_type = self._get_mime_type(str(full_path))
                
                # Gửi response header
                response_header = (
                    f'HTTP/1.1 200 OK\r\n'
                    f'Content-Type: {mime_type}\r\n'
                    f'Content-Length: {len(content)}\r\n'
                    f'Connection: close\r\n'
                    f'\r\n'
                )
                
                client_socket.sendall(response_header.encode('utf-8'))
                
                # Gửi content (trừ khi là HEAD request)
                if method == 'GET':
                    client_socket.sendall(content)
                
                self.logger.info(f'{client_ip}:{client_port} - 200: {file_path} ({len(content)} bytes)')
            
            except Exception as e:
                self.logger.error(f'{client_ip}:{client_port} - Lỗi xử lý request: {e}')
                self._send_response(client_socket, 500, 'Internal Server Error', 'Lỗi server nội bộ\n')
        
        except Exception as e:
            self.logger.error(f'{client_ip}:{client_port} - Lỗi kết nối: {e}')
        
        finally:
            # Đóng client socket
            try:
                client_socket.close()
            except:
                pass
    
    def _handle_api(self, client_socket, method, path, request_data, client_ip, client_port):
        """
        Xử lý API requests
        
        Args:
            client_socket: Socket của client
            method (str): HTTP method
            path (str): Đường dẫn API
            request_data (bytes): Dữ liệu request
            client_ip (str): IP client
            client_port (int): Port client
        """
        try:
            if path == '/api/test-results' and method == 'POST':
                # Parse request body
                try:
                    request_str = request_data.decode('utf-8', errors='ignore')
                    # Tách header và body
                    header_end = request_str.find('\r\n\r\n')
                    if header_end != -1:
                        body_str = request_str[header_end + 4:]
                        # Parse JSON từ body
                        test_data = json.loads(body_str)
                        
                        # Lưu kết quả test
                        with self._results_lock:
                            self.test_results = test_data
                        
                        self.logger.info(f'{client_ip}:{client_port} - POST /api/test-results - Lưu {len(test_data.get("results", []))} kết quả test')
                        
                        # Trả về response JSON
                        response_body = json.dumps({
                            'success': True,
                            'message': 'Đã lưu kết quả test',
                            'count': len(test_data.get('results', []))
                        })
                        
                        response_header = (
                            'HTTP/1.1 200 OK\r\n'
                            'Content-Type: application/json; charset=utf-8\r\n'
                            f'Content-Length: {len(response_body.encode("utf-8"))}\r\n'
                            'Connection: close\r\n\r\n'
                        )
                        
                        client_socket.sendall(response_header.encode('utf-8'))
                        client_socket.sendall(response_body.encode('utf-8'))
                except json.JSONDecodeError:
                    self._send_response(client_socket, 400, 'Bad Request', 'Invalid JSON')
            
            elif path == '/api/test-results' and method == 'GET':
                # Trả về kết quả test hiện tại
                with self._results_lock:
                    response_body = json.dumps(self.test_results)
                
                response_header = (
                    'HTTP/1.1 200 OK\r\n'
                    'Content-Type: application/json; charset=utf-8\r\n'
                    f'Content-Length: {len(response_body.encode("utf-8"))}\r\n'
                    'Connection: close\r\n\r\n'
                )
                
                client_socket.sendall(response_header.encode('utf-8'))
                client_socket.sendall(response_body.encode('utf-8'))
            
            elif path == '/api/logs' and method == 'GET':
                # Trả về server logs
                with self.logger._lock:
                    logs = list(self.logger.log_buffer)
                
                response_body = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'logs': logs
                })
                
                response_header = (
                    'HTTP/1.1 200 OK\r\n'
                    'Content-Type: application/json; charset=utf-8\r\n'
                    f'Content-Length: {len(response_body.encode("utf-8"))}\r\n'
                    'Connection: close\r\n\r\n'
                )
                
                client_socket.sendall(response_header.encode('utf-8'))
                client_socket.sendall(response_body.encode('utf-8'))
            else:
                self._send_response(client_socket, 404, 'Not Found', 'API endpoint không tồn tại\n')
        
        except Exception as e:
            self.logger.error(f'{client_ip}:{client_port} - Lỗi xử lý API: {e}')
            self._send_response(client_socket, 500, 'Internal Server Error', 'Lỗi server nội bộ\n')
    
    def _is_safe_path(self, file_path):
        """
        Kiểm tra path có an toàn (không bị path traversal attack)
        
        Args:
            file_path (str): Đường dẫn file từ request
        
        Returns:
            bool: True nếu safe, False nếu không
        """
        try:
            # Normalize path bằng cách loại bỏ .. và .
            # Sử dụng public_dir như là root
            file_path = file_path.lstrip('/')
            
            # Kiểm tra nếu path chứa ..
            if '..' in file_path or file_path.startswith('/'):
                return False
            
            # Xây dựng full path
            full_path = (self.public_dir / file_path).resolve()
            
            # Kiểm tra nếu resolved path nằm trong public_dir
            full_path.relative_to(self.public_dir.resolve())
            return True
        except (ValueError, RuntimeError):
            return False
    
    def _get_mime_type(self, file_path):
        """
        Xác định MIME type của file
        
        Args:
            file_path (str): Đường dẫn file
        
        Returns:
            str: MIME type
        """
        ext = Path(file_path).suffix.lower()
        
        if ext in self.MIME_TYPES:
            return self.MIME_TYPES[ext]
        
        # Fallback to mimetypes module
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'
    
    def _send_response(self, client_socket, status_code, status_message, content, is_binary=False):
        """
        Gửi HTTP response
        
        Args:
            client_socket: Socket của client
            status_code (int): HTTP status code
            status_message (str): HTTP status message
            content: Nội dung response
            is_binary (bool): Nếu True, content là bytes; False là string
        """
        try:
            # Build response header
            response_header = (
                f'HTTP/1.1 {status_code} {status_message}\r\n'
                f'Content-Type: text/html; charset=utf-8\r\n'
            )
            
            # Convert content nếu cần
            if is_binary:
                content_bytes = content
            else:
                content_bytes = content.encode('utf-8') if isinstance(content, str) else content
            
            response_header += f'Content-Length: {len(content_bytes)}\r\n'
            response_header += 'Connection: close\r\n\r\n'
            
            # Gửi response
            client_socket.sendall(response_header.encode('utf-8'))
            client_socket.sendall(content_bytes)
        
        except Exception as e:
            self.logger.error(f'Lỗi gửi response: {e}')


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
