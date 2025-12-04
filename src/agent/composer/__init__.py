"""
Composer Package

This package provides functionality to compose agents from configuration files.
"""

from .deep_agent_composer import (
    load_config,
    make_backend,
    create_middleware_list,
    create_subagents,
    compose_agent_from_yaml
)

__all__ = [
    "load_config",
    "make_backend",
    "create_middleware_list",
    "create_subagents",
    "compose_agent_from_yaml"
]