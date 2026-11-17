FROM python:3.11-slim

# Chay bang user thuong, khong phai root
RUN useradd --create-home --uid 10001 svmg && mkdir -p /app && chown svmg:svmg /app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=svmg:svmg . .

USER svmg
EXPOSE 8000

# LUU Y: context build la ../backend nen thu muc contracts/ KHONG nam trong image.
# Khi chay container hay mount contracts/schemas va dat CONTRACTS_DIR (xem infra/docker-compose.yml, phan cua M4).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
