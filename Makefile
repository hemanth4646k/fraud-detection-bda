PYTHON ?= python3.11
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: setup infra-up infra-down download train produce stream dashboard test compile

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

infra-up:
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down -v

download:
	$(PY) -m fraud_detection.download

train:
	$(PY) -m fraud_detection.train

produce:
	$(PY) -m fraud_detection.producer

stream:
	$(PY) -m fraud_detection.streaming

dashboard:
	$(PY) -m streamlit run dashboard/app.py

test:
	$(PYTHON) -m unittest discover -s tests -v

compile:
	$(PYTHON) -m compileall src dashboard tests
