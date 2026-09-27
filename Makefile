.PHONY: help repo-check pi-bootstrap pi-verify infra-bootstrap infra-verify backup restore-test test

help:
	@printf '%s\n' \
	  'BirdNET-Pi Monitoring operator targets:' \
	  '  make repo-check       - check Git for environment-specific leakage' \
	  '  make pi-bootstrap     - deploy Pi collectors/Alloy (sudo)' \
	  '  make pi-verify        - verify Pi integration (sudo)' \
	  '  make infra-bootstrap  - deploy PostgreSQL/Loki/ML timers (sudo)' \
	  '  make infra-verify     - verify infra services (sudo)' \
	  '  make backup           - create/validate BirdNET PostgreSQL dump' \
	  '  make restore-test     - restore newest dump into temporary DB' \
	  '  make test             - run ML regression tests'

repo-check:
	bash scripts/repo_check.sh

pi-bootstrap:
	sudo bash deploy/birdnet-pi/bootstrap.sh

pi-verify:
	sudo bash deploy/birdnet-pi/verify.sh

infra-bootstrap:
	sudo bash deploy/ubuntu-infra/bootstrap.sh

infra-verify:
	sudo bash deploy/ubuntu-infra/verify.sh

backup:
	bash backup/backup_infra_postgres.sh

restore-test:
	bash backup/restore_test.sh

test:
	.venv/bin/python -m unittest discover -s ml/tests -v
