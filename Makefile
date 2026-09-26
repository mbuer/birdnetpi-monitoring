.PHONY: help repo-check pi-bootstrap pi-verify infra-bootstrap infra-verify test

help:
	@printf '%s\n' \
	  'BirdNET-Pi Monitoring operator targets:' \
	  '  make repo-check       - check Git for environment-specific leakage' \
	  '  make pi-bootstrap     - deploy Pi collectors/Alloy (sudo)' \
	  '  make pi-verify        - verify Pi integration (sudo)' \
	  '  make infra-bootstrap  - deploy PostgreSQL/Loki/ML timers (sudo)' \
	  '  make infra-verify     - verify infra services (sudo)' \
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

test:
	.venv/bin/python -m unittest discover -s ml/tests -v
