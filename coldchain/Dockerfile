FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY coldchain/requirements.txt ./coldchain/requirements.txt
RUN pip install --no-cache-dir -r coldchain/requirements.txt

COPY coldchain ./coldchain

EXPOSE 8100
CMD ["python", "-m", "coldchain.api.main"]
