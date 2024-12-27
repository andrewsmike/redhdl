PHONY = lint lint_actual test test_actual vhdl_parser

# Normally, we want to provide a TTY for better formatting and interactivity.
# When invoking build commands from pre-commit, no TTY is available -
# `docker-compose run` fails unless you explicitly tell it to not expect a TTY.
# Use `make my_command` and `make my_command NO_TTY=true`, respectively.
ifeq ($(NO_TTY), true)
  TTY_FLAG=-T
else
  TTY_FLAG=-t
endif

vhdl_parser:
	docker-compose run --build --rm $(TTY_FLAG) python setup.py gen_parser

lint:
	docker-compose run --build --rm $(TTY_FLAG) test make lint_local

lint_local:
	ruff check --fix && ruff format

build:
	docker-compose build test

debug:
	docker-compose run --build --rm $(TTY_FLAG) test /bin/bash

test:
	docker-compose run --build --rm $(TTY_FLAG) test make test_local

test_local:
	mypy . && pytest .
