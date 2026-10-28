# make data H=80 | make build | make sweep HEIGHTS=40,60,80 | make all
PY ?= $(or $(SCAD_PY),$(wildcard .venv/bin/python),python3)
IMAGE ?= ../../initial1.jpg
H ?= 80
HEIGHTS ?= 40,60,80,100
ARGS ?=

.PHONY: all data build sweep clean
all: data build

data:
	$(PY) tools/make_data.py $(IMAGE) --lamp-height $(H) $(ARGS)

build:
	PY=$(PY) tools/build.sh

sweep:
	$(PY) tools/sweep.py $(IMAGE) --heights $(HEIGHTS) $(ARGS)

clean:
	rm -rf out
