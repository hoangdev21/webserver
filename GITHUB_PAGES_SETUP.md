# 🚀 GitHub Pages Setup Guide

## Cấu Hình GitHub Pages

### Bước 1: Kích hoạt GitHub Pages

1. Vào **Settings** của repository trên GitHub
2. Chọn **Pages** (bên trái menu)
3. Chọn **Source**: `GitHub Actions`
4. GitHub sẽ tự động deploy khi có push

### Bước 2: Tự động Deploy (đã cấu hình)

File `.github/workflows/deploy.yml` đã được tạo. Khi bạn push code:
- GitHub Actions sẽ chạy tự động
- Sẽ copy toàn bộ folder `public/` sang branch `gh-pages`
- Site sẽ live tại: `https://hoangdev21.github.io/webserver`

### Bước 3: Commit & Push

```bash
git add .
git commit -m "Setup GitHub Pages"
git push origin main
```

### Bước 4: Kiểm tra Deploy

1. Vào **Actions** tab trên GitHub
2. Chờ workflow `Deploy to GitHub Pages` chạy xong ✅
3. Truy cập trang web tại: `https://hoangdev21.github.io/webserver`

## ⚠️ Chú ý quan trọng

### Nếu gặp lỗi 404 trên các page khác (không phải index)

Vì GitHub Pages không có server chạy ở backend, cần cấu hình routing:

**Giải pháp 1**: Dùng Hash-based routing
- Thay URL từ `/about.html` → `/#/about.html`
- Cập nhật tất cả links trong HTML

**Giải pháp 2**: Tạo file `_config.yml` cho Jekyll (nếu cần)

```yaml
include:
  - .nojekyll
```

**Giải pháp 3** (Đơn giản nhất): Tạo `404.html` redirect

File `public/404.html` đã có, nó sẽ tự động xử lý 404 trên routing SPA.

## 📍 Base URL

Nếu site không hiển thị đúng style.css, có thể cần thêm base URL:

```html
<base href="/webserver/">
```

Thêm vào `<head>` của `index.html` nếu cần.

## 🔄 Quá trình Deploy

```
Push to main branch
       ↓
GitHub Actions trigger
       ↓
Copy public/ → gh-pages branch
       ↓
GitHub Pages build & publish
       ↓
Live at: https://hoangdev21.github.io/webserver ✨
```

## 🧪 Test Locally

```bash
# Chạy local server để test trước khi push
python server.py

# Mở: http://localhost:5000
```

## 📱 URL của site

**Repository URL**: `https://github.com/hoangdev21/webserver`
**Site URL**: `https://hoangdev21.github.io/webserver`

Nếu bạn muốn dùng custom domain, cấu hình trong **Settings > Pages > Custom domain**
