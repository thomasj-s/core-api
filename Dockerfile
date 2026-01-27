# Official python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /core-api

 # Copy poetry and project files
COPY pyproject.toml poetry.lock* /core-api

# Install poetry
RUN pip install --no-cache-dir poetry

# Call poetry to install dependencies
RUN poetry install --only main --no-root

# Copy application source code
COPY app /core-api/app

# Expose the application port
EXPOSE 8000

# Command to run the application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

