include .make/base.mk

ANSIBLE_COLLECTIONS := ./roles/
ANSIBLE_LINT_CONFIG = .ansible-lint

ansible-lint:
	@echo Discovered Roles:
	ansible-galaxy role list --roles-path ${ANSIBLE_COLLECTIONS}
	ansible-lint -c ${ANSIBLE_LINT_CONFIG} ${ANSIBLE_COLLECTIONS} > ansible-lint-results.txt