FROM python:3.12-slim
WORKDIR /app
COPY Server/requirements.txt ./Server/requirements.txt
RUN pip install --no-cache-dir -r Server/requirements.txt
COPY . ./
EXPOSE 39001
CMD ["python", "Server/project_a_server.py", "--host", "0.0.0.0", "--port", "39001"]
