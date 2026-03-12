FROM python:3.11-slim

# Install Chromium + ChromeDriver for headless perf rendering (Selenium)
RUN apt-get clean && rm -rf /var/lib/apt/lists/* \
    && apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Selenium 4 looks for "google-chrome" / "chrome", not "chromium"
RUN ln -sf /usr/bin/chromium /usr/bin/google-chrome \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome-stable

WORKDIR /app

# Install Python deps: spytial-diagramming (+ selenium), Jupyter, nbconvert
COPY requirements.txt .
RUN pip install --no-cache-dir \
        -r requirements.txt \
        jupyterlab \
        nbconvert \
        ipykernel \
        selenium

# Register a kernel so nbconvert --execute can find it
RUN python -m ipykernel install --name python3 --display-name "Python 3"

# Copy source and support files
COPY src/ src/
COPY run_perf.py .
COPY selenium_chrome_patch.py .

# Install patch as a .pth file so it auto-loads on every Python startup
RUN SITE_DIR=$(python -c "import site; print(site.getsitepackages()[0])") \
    && cp selenium_chrome_patch.py "$SITE_DIR/" \
    && echo "import selenium_chrome_patch" > "$SITE_DIR/selenium_chrome_patch.pth"

COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Results directory (mount a volume here to retrieve perf output)
RUN mkdir -p results

EXPOSE 8888

ENTRYPOINT ["./docker-entrypoint.sh"]
