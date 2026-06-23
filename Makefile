.PHONY: install test preflight simulate start list

install:
	python -m pip install -r requirements-dev.txt

test:
	pytest

preflight:
	python preflight.py

simulate:
	python simulate.py --scenario SCN-01

start:
	python start.py

list:
	python run_calls.py --list
