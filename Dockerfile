FROM python:3.12-slim

# chromium and its matching driver come from Debian's repositories, so no driver is downloaded at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BINARY=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# bind to all interfaces so the port can be published from the container
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
