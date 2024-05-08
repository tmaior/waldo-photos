FROM python:3.8.5 as builder

RUN mkdir /app
WORKDIR /app

RUN pip install pipenv
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

COPY common common
RUN PYTHONUSERBASE=/pyroot PIP_USER=1 PIP_IGNORE_INSTALLED=1 pipenv install --system --deploy --ignore-pipfile


FROM python:3.8.5-slim-buster

# copy in python deps from earlier build stage
COPY --from=builder /pyroot/lib/ /usr/local/lib/
RUN pip install six  # not sure why this is needed now when it wasn't before
RUN pip install certifi  # not sure why this is needed now when it wasn't before

RUN apt update
RUN apt install dumb-init

RUN mkdir /app
WORKDIR /app

COPY common common
RUN pip install -e common # not sure why this is needed now when it wasn't before

COPY waldo_cdc waldo_cdc
COPY tests tests
COPY scripts scripts

EXPOSE 5000

ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD ["scripts/start"]
