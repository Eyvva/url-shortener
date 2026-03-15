FROM redhat/ubi9-minimal:latest

WORKDIR /app

RUN microdnf install -y python3 python3-pip gcc python3-devel libpq-devel && \
    microdnf clean all

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
