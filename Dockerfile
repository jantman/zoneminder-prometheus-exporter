FROM python:3.14.3-trixie

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt && \
    sed -i "s/.decode()/.decode(errors='replace')/g" \
        /usr/local/lib/python3.14/site-packages/pyzm/ZMMemory.py
COPY main.py /main.py

EXPOSE 8080

ENTRYPOINT [ "/bin/sh", "-c", "/main.py ${@}", "--" ]
