FROM python:3.12-alpine

COPY requirements.txt /requirements.txt
COPY main.py /main.py
RUN pip install -r /requirements.txt

EXPOSE 8080

ENTRYPOINT [ "/bin/sh", "-c", "/main.py ${@}", "--" ]
