RedHDL: Verilog -> Redstone Circuits.
=====================================
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Redstone circuit synthesizer for the rapid prototyping of large-scale redstone circuits.
Nearing MVP of "can place and bus moderately sized circuits from an existing library in a not-braindead way".


Setting up
----------
```sh
$ pip install -e .
$ pip install pre-commit; pre-commit install
```

Running tests:
```sh
$ pytest -k my_test_name
```
