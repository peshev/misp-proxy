FROM nginx

RUN apt update && apt install -y python3 python3-pip

RUN mkdir /app
WORKDIR /app

COPY src/requirements.txt .
RUN pip3 install -r requirements.txt
COPY src/misp-proxy.sh /docker-entrypoint.d

COPY src/misp-proxy.conf.j2 .
COPY src/misp-proxy.py .

