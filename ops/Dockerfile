FROM python:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache --upgrade -r /code/requirements.txt

CMD ["tail", "-f", "/dev/null"]