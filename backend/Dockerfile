FROM python:3.12-slim

WORKDIR /app

# Copy ML model + backend
COPY Behavioural-model/ ./Behavioural-model/
COPY backend/ ./backend/
COPY DataSet.csv ./DataSet.csv

# Install dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
