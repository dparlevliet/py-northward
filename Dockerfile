FROM python:3.12

WORKDIR /app
COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

WORKDIR /src
COPY src/ .

CMD ["tail", "-f", "/dev/null"]