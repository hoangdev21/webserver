# 🔧 Cách sửa lỗi CSS trên GitHub Pages

## Vấn đề
- Local server (http://localhost:5000) có CSS ✅
- GitHub Pages (https://hoangdev21.github.io/webserver/) không có CSS ❌

## Nguyên nhân
GitHub Pages đang serve từ `gh-pages` branch nhưng có thể chưa cập nhật hoặc cần cấu hình Settings.

## Giải pháp

### Bước 1: Kiểm tra & Cấu hình GitHub Pages

1. Vào **Settings** → **Pages** trên GitHub
2. Chọn **Source**: 
   - Nếu là `Deploy from branch`, chọn branch `gh-pages`
   - Nếu là `GitHub Actions`, đảm bảo workflow chạy thành công

### Bước 2: Kiểm tra Workflow chạy thành công

1. Vào tab **Actions** trên GitHub
2. Xem workflow `Deploy to GitHub Pages`
3. Kiểm tra xem có ❌ hay ✅
4. Nếu có lỗi, sửa và re-run

### Bước 3: Xóa GitHub Pages Cache

Nếu vẫn không có CSS, thực hiện:

1. **Vào Settings → Pages**
2. **Thay đổi Source** từ `gh-pages` → `None`
3. **Chờ** vài giây
4. **Quay lại** chọn `Deploy from a branch` → `gh-pages`

### Bước 4: Cấu hình Alternative - Dùng ROOT folder

Nếu muốn đơn giản hơn, có thể move `public/` → root và cấu hình:

```bash
# Thay vì publish_dir: ./public
# Sử dụng publish_dir: ./
```

## Kiểm tra URL trong Browser

**Đúng:**
```
https://hoangdev21.github.io/webserver/
https://hoangdev21.github.io/webserver/style.css
https://hoangdev21.github.io/webserver/index.html
```

**Sai (sẽ dẫn đến 404):**
```
https://hoangdev21.github.io/style.css ❌
https://hoangdev21.github.io/index.html ❌
```

## Debug: Mở DevTools

Khi vào website:
1. Nhấn **F12** (mở DevTools)
2. Vào tab **Console** hoặc **Network**
3. Tìm request `style.css` 
4. Kiểm tra Status Code:
   - **200** = OK ✅
   - **404** = File không tìm thấy ❌

## Nếu vẫn không hoạt động

Hãy thử:**Clear all and redeploy**:

```bash
# 1. Xóa branch gh-pages
git push origin --delete gh-pages

# 2. Commit mới
git add .
git commit -m "Clear GitHub Pages"
git push origin main

# 3. GitHub Actions sẽ tạo lại gh-pages tự động
```

## Tức thì kiểm tra

Sau khi push, workflow chạy khoảng **1-2 phút**. Sau đó:
- Vào: https://hoangdev21.github.io/webserver/
- Mở DevTools (F12)
- Xem Network tab
- Check xem style.css load được không

## Câu hỏi kiểm tra

**Q: Tại sao local có CSS nhưng GitHub Pages không?**
A: Vì local serve từ `/public/` nhưng GitHub Pages serve từ `/webserver/` (subfolder). Đường dẫn CSS phải là `./style.css` (relative) để hoạt động ở cả hai chỗ.

**Q: Nếu còn không hoạt động?**
A: GitHub Pages cần `10-15 phút` để fully propagate. Hãy đợi rồi clear cache browser (Ctrl+Shift+Delete).
