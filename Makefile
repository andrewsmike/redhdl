PHONY = lint lint_actual test test_actual


gen_parser:
	docker-compose run --build --rm python setup.py gen_parser

lint:
	docker-compose run --build test make lint_actual

lint_actual:
	black . && isort . && flake8 .

debug:
	docker-compose run --build --rm test /bin/bash

test:
	docker-compose run --build --rm test make test_actual

test_actual:
	mypy . && pytest .
