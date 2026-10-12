.PHONY: install auth run once test check

install:
	poetry install
	poetry run pre-commit install

auth:
	poetry run sync-app auth

run:
	poetry run sync-app run

once:
	poetry run sync-app run --once

test:
	poetry run pytest

check:
	poetry run pre-commit run --all-files
