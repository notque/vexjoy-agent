"""Skill evaluation and description optimization toolkit.

Ported from Anthropic's skill-creator (https://github.com/anthropics/skills).
Adapted for the agents repo architecture.

Usage:
    python -m scripts.skill_eval.run_eval --eval-set evals.json --skill-path path/to/skill
    python -m scripts.skill_eval.run_loop --eval-set evals.json --skill-path path/to/skill --model claude-opus-4-6
    python -m scripts.skill_eval.quick_validate path/to/skill
"""
