# ==========================================
# STAGE 1: Copy uv binary
# ==========================================
FROM ghcr.io/astral-sh/uv:latest AS uv_bin

# ==========================================
# STAGE 2: Final Runtime
# ==========================================
FROM python:3.10-slim

WORKDIR /app

# Copy công cụ uv trực tiếp vào thư mục bin của hệ thống (đã có sẵn trong PATH)
COPY --from=uv_bin /uv /usr/local/bin/uv

# Thiết lập biến môi trường để uv tự động cài đặt vào system Python (không cần venv trong container)
ENV UV_SYSTEM_PYTHON=1

# Copy danh sách dependency
COPY requirements.txt .

# Sử dụng cache mount của uv (mặc định tại /root/.cache/uv) để cài đặt siêu tốc
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt

# Tải trước model embedding và đóng gói vào image (đảm bảo chạy offline ổn định)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy mã nguồn ứng dụng
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
