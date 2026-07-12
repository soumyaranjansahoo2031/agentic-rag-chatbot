FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt .

RUN pip install --upgrade pip

RUN pip install \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD streamlit run streamlit_frontend_rag_yt.py \
    --server.address=0.0.0.0 \
    --server.port=$PORT \
    --server.headless=true \
    --browser.gatherUsageStats=false