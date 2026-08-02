FROM python:3.12-slim

WORKDIR /app

# build-essential and cmake are needed to build llama-cpp-python when no
# prebuilt wheel is available for the current platform.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

EXPOSE 5000

# --workers 1: the model is kept as a single in-memory instance.
# --timeout 600: CPU generation of long outputs can take minutes.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "600", "app:app"]
