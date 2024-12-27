PHONY = lint lint_actual test test_actual vhdl_parser


vhdl_parser:
	docker-compose run --build --rm -T python setup.py gen_parser

lint:
	docker-compose run --build --rm -T test make lint_local

lint_local:
	ruff check --fix && ruff format

build:
	docker-compose build test

debug:
	docker-compose run --build --rm test /bin/bash

test:
	docker-compose run --build --rm -T test make test_local

test_local:
	mypy . && pytest .
