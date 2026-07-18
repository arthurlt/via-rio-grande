.PHONY: check build

build:
	hugo --panicOnWarning

check:
	python3 scripts/validate_site.py
