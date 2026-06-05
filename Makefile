# VexJoy Agent — make targets.
#
# skill-eval-ablation: local before/after eval for skills changed in a range
# (ADR skill-eval-pr-ablation). Runs the real eval via the `claude` CLI, prints
# the base->head delta, and (with RECORD=1) records each run to learning.db.
# Advisory — never blocks anything.
#
#   make skill-eval-ablation BASE=<ref> HEAD=<ref> [SKILL=<name>] [RUNS=3] [RECORD=1]
#   make skill-eval-install-hook    # write the opt-in pre-push hook

PYTHON ?= python3
BASE ?= HEAD~1
HEAD ?= HEAD
RUNS ?= 3
SKILL ?=
RECORD ?=

ABLATION_ARGS := --base $(BASE) --head $(HEAD) --runs $(RUNS)
ifneq ($(strip $(SKILL)),)
ABLATION_ARGS += --skill $(SKILL)
endif
ifneq ($(strip $(RECORD)),)
ABLATION_ARGS += --record
endif

.PHONY: skill-eval-ablation skill-eval-install-hook

skill-eval-ablation:
	$(PYTHON) scripts/skill-eval-ablation.py $(ABLATION_ARGS)

skill-eval-install-hook:
	$(PYTHON) scripts/skill-eval-ablation.py --install-hook
