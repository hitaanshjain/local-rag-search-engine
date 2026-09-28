# 1. Use a lightweight Python Linux image
FROM python:3.13-slim

# 2. Set the working directory inside the container
WORKDIR /app

# OpenCV in the ingestion group needs these shared libraries in slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0t64 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Install our modern package manager
RUN pip install --no-cache-dir uv

# 4. Copy the lockfile and project definitions first
COPY pyproject.toml uv.lock ./

# 5. Install dependencies and bundled OCR models from the lockfile so the
# same image can ingest new PDFs after transfer to an offline machine.
RUN uv sync --frozen

# Runtime uv commands must fail if a required package is missing locally.
ENV UV_OFFLINE=1

# 6. Copy the rest of the application code
COPY . .

# 7. Expose the port the app runs on
EXPOSE 8000

# 8. The command to run the app using uv, pointing to the new app directory
CMD ["uv", "run", "--frozen", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
