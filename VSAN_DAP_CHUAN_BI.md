# 📝 Chuẩn Bị Vấn Đáp - Web Server Tĩnh Đa Luồng

## 🎯 Thông Tin Dự Án
- **Đề tài**: Web Server Tĩnh Hỗ trợ Đa Luồng (Threading)
- **Nâng cấp từ**: Web Server Tĩnh (đơn luồng)
- **Công nghệ**: socket, HTTP, threading
- **Thách thức chính**: Kết hợp HTTP và concurrency để xây dựng server hiệu năng cao

---

## 🤔 CÂU HỎI KIẾN THỨC CƠ BẢN - HTTP

### 1. **HTTP là gì? Tại sao lại chọn HTTP cho dự án này?**
**Câu trả lời gợi ý:**
- HTTP (HyperText Transfer Protocol) là giao thức tầng ứng dụng (Layer 7)
- Sử dụng mô hình request-response
- Chọn HTTP vì:
  - Là giao thức chuẩn cho web
  - Đơn giản để implement
  - Có sẵn các client (browser, curl, requests)
  - Phù hợp với bài tập học tập

### 2. **HTTP methods nào được hỗ trợ trong project?**
**Câu trả lời gợi ý:**
- Hiện tại hỗ trợ: **GET** và **HEAD**
- Code ở [server.py](server.py#L272):
  ```python
  if method == 'GET':
      # Serve file
  elif method == 'HEAD':
      # Like GET but without body
  else:
      # 405 Method Not Allowed
  ```
- Lý do không hỗ trợ POST/PUT/DELETE: đây là server tĩnh, chỉ serve files

### 3. **HTTP status codes nào được trả về?**
**Câu trả lời gợi ý:**
| Code | Tình Huống |
|------|-----------|
| 200 | File tìm thấy OK |
| 304 | Not Modified (TODO caching) |
| 400 | Bad Request (request không hợp lệ) |
| 403 | Forbidden (path traversal) |
| 404 | File không tồn tại |
| 405 | Method không hỗ trợ |
| 500 | Lỗi server |
| 501 | Not Implemented |

**Xem code:** [server.py#L129-L135](server.py#L129-L135)

### 4. **HTTP request structure là gì?**
**Câu trả lời gợi ý:**
```
GET /index.html HTTP/1.1
Host: localhost:8000
Connection: close
[empty line]
```
- Request line: `METHOD PATH HTTP/VERSION`
- Headers: key-value pairs
- Empty line
- Body (optional)

**Code parse request:** [server.py#L258-L290](server.py#L258-L290)

### 5. **HTTP response structure là gì?**
**Câu trả lời gợi ý:**
```
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 1024
Connection: close
[empty line]
[body content]
```

**Code tạo response:** [server.py#L419-L422](server.py#L419-L422)

---

## 🤔 CÂU HỎI KIẾN THỨC THREADING - CONCURRENCY

### 6. **Tại sao cần threading? Nêu sự khác biệt giữa single-threaded và multi-threaded server**

**Câu trả lời gợi ý:**

**Single-threaded (trước đó):**
```
Client 1 requests → Server xử lý (block)
  ↓
Client 2 requests → Chờ Client 1 xong
  ↓
Client 3 requests → Chờ Client 2 xong
```
- **Vấn đề**: Chỉ phục vụ 1 client lúc 1, throughput thấp
- **Timeout**: Client 2, 3 bị block lâu

**Multi-threaded (hiện tại):**
```
Client 1 requests → Thread 1 xử lý (không block)
Client 2 requests → Thread 2 xử lý (song song)
Client 3 requests → Thread 3 xử lý (song song)
```
- **Lợi ích**: Phục vụ nhiều clients cùng lúc
- **Throughput cao hơn**
- **Response time đều hơn**

**Code:** [server.py#L175-L182](server.py#L175-L182)
```python
self.executor = ThreadPoolExecutor(
    max_workers=self.max_threads,
    thread_name_prefix='HTTPWorker'
)
```

### 7. **ThreadPoolExecutor là gì? Tại sao lại dùng nó thay vì tạo thread trực tiếp?**

**Câu trả lời gợi ý:**
- ThreadPoolExecutor: quản lý pool của các threads
- Tạo sẵn N threads, tái sử dụng chúng
- **Lợi ích:**
  - Giảm overhead tạo/hủy threads (mất tài nguyên)
  - Kiểm soát số threads (không tạo vô hạn)
  - Auto queue management
  - Dễ cleanup (shutdown)

**So sánh:**
```python
# ❌ Direct threading - tạo thread mới mỗi request
for client in clients:
    t = threading.Thread(target=handle, args=(client,))
    t.start()
    # Problem: Create 1000 threads = resource exhaustion!

# ✓ ThreadPoolExecutor - tái sử dụng
executor = ThreadPoolExecutor(max_workers=10)
for client in clients:
    executor.submit(handle, client)
    # Max 10 threads, queue requests tự động
```

**Code:** [server.py#L175](server.py#L175)

### 8. **Race condition là gì? Đã xảy ra trong project không?**

**Câu trả lời gợi ý:**
- **Race condition**: 2 threads cùng access shared resource → inconsistent state
- **Ví dụ**: 2 threads ghi log cùng lúc → logs bị lẫn lộn

**Trong project:**
- **Tiềm ẩn**: Logger ghi file từ nhiều threads
- **Giải pháp**: Sử dụng `threading.Lock()`
  
**Code:** [server.py#L73-L77](server.py#L73-L77)
```python
def info(self, msg):
    with self._lock:  # Thread-safe block
        self.logger.info(msg)
        self.them_vao_bo_dem(...)
```

### 9. **Thread safety là gì? Làm sao bảo vệ shared data?**

**Câu trả lời gợi ý:**
- **Thread safety**: Code hoạt động đúng khi execute từ nhiều threads
- **Các cách bảo vệ:**
  1. **Lock (Mutex)**: Chỉ 1 thread vào critical section
  2. **Read-Write Lock**: Nhiều readers, 1 writer
  3. **Atomic operations**: CPU đảm bảo atomic
  4. **Thread-local storage**: Mỗi thread có copy riêng

**Trong project:**
```python
self._lock = threading.Lock()

# Critical section
with self._lock:
    # Chỉ 1 thread execute at a time
    self.log_buffer.append(msg)
```

### 10. **Deadlock có thể xảy ra không? Làm sao tránh?**

**Câu trả lời gợi ý:**
- **Deadlock**: Thread A chờ lock của B, B chờ lock của A → stuck forever
- **Trong project**: 
  - Chỉ có 1 lock (logger) → **Không thể deadlock**
  - Nếu có 2+ locks → cần cẩn thận về thứ tự acquire
  
**Tránh deadlock:**
1. Acquire locks theo thứ tự cố định
2. Minimize critical section
3. Không gọi function bên ngoài khi holding lock

---

## 🤔 CÂU HỎI KIẾN THỨC SOCKET PROGRAMMING

### 11. **Socket là gì? Client-server model hoạt động như thế nào?**

**Câu trả lời gợi ý:**
- **Socket**: Endpoint của network communication (giống như "đầu nối" mạng)
- **Client-Server model**:
  ```
  Server socket (listen)
  ↓
  Client connects
  ↓
  Accept → connection socket
  ↓
  Communicate
  ```

**Code server:**
```python
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((host, port))
server_socket.listen(5)  # Max 5 pending connections

while True:
    conn_socket, addr = server_socket.accept()  # Block chờ client
    # Handle client
```

**Code client:**
```python
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((host, port))
client_socket.send(request)
response = client_socket.recv(8192)
client_socket.close()
```

### 12. **Sự khác biệt giữa TCP và UDP?**

**Câu trả lời gợi ý:**
| Đặc điểm | TCP | UDP |
|---------|-----|-----|
| Connection | Có (3-way handshake) | Không (connectionless) |
| Reliability | Đảm bảo delivery | Best-effort |
| Ordering | Đảm bảo thứ tự | Không |
| Speed | Chậm hơn | Nhanh hơn |
| Use case | HTTP, FTP, SSH | DNS, Video streaming |

**Trong project:** Dùng TCP (socket.SOCK_STREAM) vì HTTP cần reliability

### 13. **Blocking vs Non-blocking socket?**

**Câu trả lời gợi ý:**
- **Blocking socket** (default):
  - `recv()` block chờ data
  - `accept()` block chờ connection
  - Thread không làm được gì khác

- **Non-blocking socket**:
  - Ngay lập tức return (không chờ)
  - Cần poll/check periodically
  - Phức tạp hơn

**Trong project:**
```python
sock.settimeout(self.timeout)  # Timeout instead of infinite block
sock.recv(8192)  # Block với timeout
```

### 14. **Làm sao handle multiple clients với socket?**

**Câu trả lời gợi ý:**

**Cách 1: Sequential** (Single-threaded)
```python
while True:
    conn, addr = server_socket.accept()
    handle_client(conn)  # Block chờ client xong
    conn.close()
```
**Problem**: 1 client = tất cả clients chờ

**Cách 2: Threading** (Multi-threaded) - **Project hiện tại**
```python
executor = ThreadPoolExecutor(max_workers=10)
while True:
    conn, addr = server_socket.accept()
    executor.submit(handle_client, conn)  # Non-block
    # Accept next client ngay lập tức
```

**Cách 3: Select/Epoll** (Async I/O)
```python
# Monitor multiple sockets với select/epoll
for readable in select.select(sockets, [], [])[0]:
    if readable == server_socket:
        conn, addr = server_socket.accept()
    else:
        handle_data(readable)
```

**Project dùng Cách 2 vì**: Simple, dễ hiểu, adequate cho bài tập

---

## 🤔 CÂU HỎI VỀ ARCHITECTURE & DESIGN

### 15. **Giải thích architecture của server?**

**Câu trả lời gợi ý:**
```
┌──────────────────────────────────────┐
│      Main Server Thread              │
│  - Bind, Listen, Accept              │
│  - Accept loop                       │
└──────────────────────────────────────┘
           ↓ (submit task)
┌──────────────────────────────────────┐
│    ThreadPoolExecutor (max_workers=10) │
│  ┌────────┐ ┌────────┐ ┌────────┐   │
│  │Worker 1│ │Worker 2│ │Worker 3│...│
│  └────────┘ └────────┘ └────────┘   │
└──────────────────────────────────────┘
           ↓
   Mỗi worker:
   1. Parse HTTP request
   2. Validate path (security)
   3. Read file
   4. Send response
   5. Log request
```

**Code:**
- [server.py#L195-L245](server.py#L195-L245) - Accept loop
- [server.py#L248-L290](server.py#L248-L290) - Handle client

### 16. **Path traversal attack là gì? Làm sao prevent?**

**Câu trả lời gợi ý:**

**Attack:**
```
GET /../../../etc/passwd HTTP/1.1
GET /..%2f..%2fetc%2fpasswd HTTP/1.1  (URL encoded)
```
Mục đích: Access files ngoài public/ directory

**Prevention trong project:**
```python
def khoa_yen_to(self, file_path):
    # Normalize path
    requested = Path(file_path).resolve()
    # Check if requested is inside public_dir
    requested.relative_to(self.public_dir)  # Raise ValueError if not
```

**Code:** [server.py#L402-L407](server.py#L402-L407)

### 17. **MIME type detection hoạt động như thế nào?**

**Câu trả lời gợi ý:**
- MIME type: Mô tả loại file (text/html, image/png, etc.)
- Browser sử dụng để biết cách render

**Project:**
```python
def xac_dinh_kieu_mime(self, file_path):
    ext = Path(file_path).suffix.lower()
    return self.MIME_TYPES.get(ext) or \
           mimetypes.guess_type(file_path)[0] or \
           'application/octet-stream'
```

**Ưu tiên:**
1. Dictionary cứng (nhanh nhất)
2. mimetypes module (phụ lục hệ thống)
3. Default: application/octet-stream

---

## 🤔 CÂU HỎI VỀ PERFORMANCE & TESTING

### 18. **Làm sao đo performance? Throughput/Latency/Scalability là gì?**

**Câu trả lời gợi ý:**
- **Throughput**: Số requests/giây (RPS)
- **Latency**: Response time một request
- **Scalability**: Performance tăng khi thêm resources

**Test tools:**
- [client_test.py](client_test.py) - Concurrent requests
- Đo min/max/avg response time
- Đo success rate

**Kết quả benchmark:**
```
50-100 req/s throughput
2-5 ms avg latency
Max 10 concurrent connections
```

### 19. **Failure simulation là gì? Tại sao cần?**

**Câu trả lời gợi ý:**
- Simulate server failures: 500, 503, 504
- **Lý do**: Test cách client handle errors
- **Config:**
  ```json
  "enable_failure_simulation": true,
  "failure_rate": 0.2  // 20% failures
  ```

**Code:** [server.py#L259-L262](server.py#L259-L262)

### 20. **Làm sao test concurrent requests?**

**Câu trả lời gợi ý:**
- [client_test.py](client_test.py) - Submit multiple requests từ thread pool
- Measure response time, success rate
- Check status codes distribution

**Ví dụ:**
```bash
python client_test.py --num-requests 100 --concurrency 10
```
- Gửi 100 requests
- 10 threads cùng lúc
- Measure throughput, latency

---

## 🤔 CÂU HỎI VỀ IMPLEMENTATION DETAILS

### 21. **Logging hoạt động như thế nào?**

**Câu trả lời gợi ý:**
- [ThreadSafeLogger](server.py#L30-L110) - Custom logger
- Thread-safe với `threading.Lock()`
- 2 outputs: file + console
- Rotating file handler (max 10MB)
- In-memory buffer (last 500 logs)

**Format:**
```
2025-12-18 14:30:00 - [HTTPWorker-1] - INFO - Request from 127.0.0.1:12345
```

### 22. **Config.json làm gì?**

**Câu trả lời gợi ý:**
Centralize configuration:
```json
{
  "host": "0.0.0.0",
  "port": 5000,
  "max_threads": 10,
  "public_dir": "public",
  "log_file": "logs/server.log",
  "timeout": 30,
  "chunk_size": 8192,
  "failure_rate": 0.0,
  "enable_failure_simulation": false
}
```

**Lợi ích:**
- Dễ thay đổi mà không edit code
- Giống production servers (nginx, Apache)

### 23. **Tại sao dùng Path.resolve() thay vì string manipulation?**

**Câu trả lời gợi ý:**
- Path.resolve(): Chuẩn hóa path (resolve .., ., symlinks)
- Cross-platform (Windows \\ vs Linux /)
- Safer: không bị trick bởi symlink

```python
# ❌ String manipulation - dễ bị trick
if path.startswith('/public/'):  # ❌ /public/../etc/passwd?

# ✓ Path.resolve()
from pathlib import Path
requested = Path(path).resolve()
requested.relative_to(public_dir)  # ✓ Safe
```

---

## 🤔 CÂU HỎI VỀ COMPARISON & IMPROVEMENTS

### 24. **So sánh với Web Server Tĩnh cũ (single-threaded)?**

**Câu trả lời gợi ý:**

| Đặc điểm | Single-threaded | Multi-threaded |
|---------|-----------------|----------------|
| Code complexity | Đơn giản | Phức tạp hơn |
| Concurrent clients | 1 | 10+ |
| Throughput | 10-20 RPS | 50-100+ RPS |
| Latency | 500-1000 ms (blocked) | 2-5 ms (parallel) |
| Resource usage | Thấp | Cao hơn |
| Real-world use | Không | Practical |

### 25. **Cái gì còn thiếu? Có thể improve gì?**

**Câu trả lời gợi ý:**

**Thiếu:**
- [ ] HTTPS/SSL
- [ ] HTTP/2
- [ ] Caching (ETag, Last-Modified)
- [ ] Gzip compression
- [ ] Range requests
- [ ] Directory listing
- [ ] File upload

**Có thể improve:**
1. **Connection pooling** - Reuse connections
2. **Async I/O** (asyncio) - Thay vì threading
3. **Load balancing** - Multiple server instances
4. **CDN** - Serve static files globally
5. **Caching layer** - Redis, Memcached

**Vì sao chưa implement:**
- Bài tập focus vào threading + HTTP
- Thêm complexity thừa
- Out of scope

### 26. **Tại sao không dùng asyncio thay vì threading?**

**Câu trả lời gợi ý:**

**Threading:**
- ✓ Đơn giản, dễ hiểu
- ✓ CPU-bound tasks
- ✗ Nhiều memory (1 thread ≈ 1MB)
- ✗ GIL (Python) - không true parallelism

**Asyncio:**
- ✓ Memory efficient (1 coroutine ≈ 1KB)
- ✓ Thousands of concurrent connections
- ✗ Phức tạp (async/await, event loop)
- ✗ Hard to debug

**Project dùng threading vì:**
- HTTP server = I/O-bound (socket operations)
- Threading đủ cho bài tập
- Code dễ hiểu hơn asyncio

---

## 🤔 CÂU HỎI TỔNG HỢP & TÌNH HUỐNG

### 27. **Nếu 1000 clients kết nối cùng lúc, server sẽ như thế nào?**

**Câu trả lời gợi ý:**
```
Config: max_threads = 10

Request 1-10: Execute ngay (threads 1-10)
Request 11-100: Queue chờ
Request 101-1000: Queue chờ
```

**Kết quả:**
- First 10: response time ≈ 2-5ms
- Next 990: response time ≈ timeout (30s)
- Clients chảy máu → TimeoutError

**Giải pháp:**
1. Tăng max_threads (nếu server có resources)
2. Dùng asyncio thay threading
3. Implement rate limiting
4. Load balance across servers

### 28. **Nếu file rất lớn (1GB), server sẽ thế nào?**

**Câu trả lời gợi ý:**
- Current: Load file vào memory, gửi
- **Problem**: OOM (Out of Memory)

**Giải pháp:**
```python
# Streaming - read chunks
with open(file_path, 'rb') as f:
    while True:
        chunk = f.read(self.chunk_size)  # 8KB at a time
        if not chunk:
            break
        sock.sendall(chunk)
```

**Project:** Đã implement chunked sending, nhưng could optimize more

### 29. **Bug: Client disconnect khi đang send file. Server sẽ crash không?**

**Câu trả lời gợi ý:**
- Server có try-except → không crash
- Log error
- Cleanup socket
- Continue serving other clients

**Code:** [server.py#L354-L356](server.py#L354-L356)
```python
finally:
    try:
        sock.close()
    except:
        pass
```

### 30. **Làm sao deploy server lên production?**

**Câu trả lời gợi ý:**
**Không nên dùng trực tiếp!**

**Production setup:**
1. Gunicorn/uWSGI - Application server
2. Nginx - Reverse proxy + load balancer
3. Supervisor - Process management
4. SSL/TLS - HTTPS
5. Monitoring - Prometheus, ELK

**Lý do:**
- Built-in server không safe/optimized
- Giống Django development server
- Cần industrial-grade server

---

## 📋 QUICK REFERENCE - ĐỀ CƯƠNG TÓM TẮT

| Category | Key Points |
|----------|-----------|
| **HTTP** | GET/HEAD methods, status codes, request/response format |
| **Threading** | ThreadPoolExecutor, thread safety, locks, race conditions |
| **Socket** | TCP/IP, blocking, client-server model |
| **Security** | Path traversal prevention, input validation |
| **Performance** | Throughput, latency, concurrent connections, bottlenecks |
| **Testing** | Load testing, failure simulation, metrics |
| **Design** | Architecture, logging, configuration, error handling |

---

## 💡 MẸO VĂN ĐÁP

1. **Hãy thực hiện demo live:**
   ```bash
   # Terminal 1: Run server
   python server.py
   
   # Terminal 2: Run test
   python client_test.py --num-requests 50 --concurrency 10
   
   # Browser: http://localhost:5000
   ```

2. **Giải thích theo flow:**
   - Client gửi request
   - Server accept vào thread
   - Parse request, validate, find file
   - Send response
   - Log everything

3. **Sẵn sàng code:**
   - Mở các file key (server.py, client_test.py)
   - Navigate tới các line numbers quan trọng
   - Giải thích từng hàm chính

4. **Chuẩn bị diagram:**
   - Architecture diagram (threads, pool)
   - Request flow
   - Security check flow

5. **Trả lời honest:**
   - Nếu không biết → nói "mình chưa implement điều đó"
   - Giải thích why ("out of scope")
   - Nêu cách improve

6. **Nhấn mạnh lợi ích threading:**
   - Concurrent handling
   - Better throughput
   - Responsive server

7. **Nếu bị hỏi về edge cases:**
   - Nói cách bạn handle nó
   - Nếu chưa handle → discuss solution

---

## 🚀 NEXT STEPS TRƯỚC VĂN ĐÁP

- [ ] Review code bên dưới:
  - [ ] [server.py](server.py) - Main logic
  - [ ] [client_test.py](client_test.py) - Testing
  - [ ] [config.json](config.json) - Configuration

- [ ] Chạy live demo:
  ```bash
  python server.py
  python client_test.py --num-requests 30 --concurrency 5
  ```

- [ ] Chuẩn bị slides/notes về:
  - [ ] Architecture
  - [ ] Thread safety
  - [ ] Security
  - [ ] Performance results

- [ ] Ghi nhớ 5 điểm chính:
  1. ThreadPoolExecutor cho concurrent handling
  2. Path traversal prevention (security)
  3. Thread-safe logging with locks
  4. HTTP parsing + response generation
  5. Throughput improvement vs single-threaded

**Good luck! 🎯**
