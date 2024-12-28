FROM python:3.10-bookworm AS redhdl

ENV REDHDL /pkg/redhdl
WORKDIR $REDHDL/

RUN apt-get update
RUN apt-get install iverilog

COPY setup.py $REDHDL/setup.py
COPY pyproject.toml $REDHDL/pyproject.toml

# Set up an editable install without any code.
# Doing this first makes for faster rebuilds; pip install is only invoked iff
# depenencies or project settings are actually changed.
RUN mkdir $REDHDL/redhdl
RUN --mount=type=cache,target=/root/.cache pip install -e .[test]

COPY redhdl $REDHDL/redhdl
COPY scripts $REDHDL/scripts
COPY tests $REDHDL/tests
COPY hdl_examples $REDHDL/hdl_examples
COPY schematics $REDHDL/schematics
COPY modules $REDHDL/modules
