FROM python:3.12-slim
WORKDIR /workspace
COPY pyproject.toml .
COPY apps ./apps
COPY packages ./packages
RUN pip install --no-cache-dir .
CMD ["python","-m","apps.scheduler.main"]
