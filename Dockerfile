# 1. Use a lightweight Python Linux image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install our modern package manager
RUN pip install --no-cache-dir uv

# 4. Copy the lockfile and project definitions first
COPY pyproject.toml uv.lock ./

# 5. Install dependencies from the lockfile
RUN uv sync --frozen

# 6. Copy the rest of the application code
COPY . .

# 7. Expose the port the app runs on
EXPOSE 8000

# 8. The command to run the app using uv, pointing to the new app directory
CMD ["uv", "run", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]