"""
Deep Agent Composer Module

This module provides functionality to compose deep agents from YAML configuration files.
"""

import yaml
from typing import Dict, Any, List
import os
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import (
    ContextEditingMiddleware, 
    ClearToolUsesEdit, 
    ModelFallbackMiddleware
)

from agent.common.config import get_models
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

from agent.middleware.important_notes import ImportantNotesMiddleware
from agent.middleware.long_chain_wake_up import LongChainWakeUp
from agent.models.agent_response import FlagResponse
from agent.tools.http_request import curl
from agent.tools.kali import get_kali_openapi_spec
from agent.tools.python_code import execute_python_code_command

main_model, backup_model = get_models()


def load_config(config_path: str) -> Dict[Any, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path (str): Path to the YAML configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    # If no config path provided, use the default config_example.yaml in the same directory
    if config_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config_example.yaml")
    # If config_path is a relative path, resolve it relative to the current file's directory
    elif not os.path.isabs(config_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, config_path)
    
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def make_backend(runtime, filesystem_config: Dict[str, Any]) -> CompositeBackend:
    """
    Create a composite backend based on configuration.
    
    Args:
        runtime: The runtime environment
        filesystem_config (dict): Filesystem backend configuration
        
    Returns:
        CompositeBackend: Configured composite backend
    """
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/memories/": StoreBackend(runtime),
            filesystem_config["route"]: FilesystemBackend(
                root_dir=filesystem_config["root_dir"],
                virtual_mode=filesystem_config.get("virtual_mode", False)
            )
        }
    )


def create_middleware_list(middleware_configs: List[Dict[str, Any]]) -> List[Any]:
    """
    Create middleware list based on configuration.
    
    Args:
        middleware_configs (list): List of middleware configurations
        
    Returns:
        list: Configured middleware list
    """
    middlewares = []
    
    for config in middleware_configs:
        middleware_type = config.get("type")
        
        if middleware_type == "ModelFallbackMiddleware":
            middlewares.append(ModelFallbackMiddleware(
                main_model,
                backup_model
            ))
        elif middleware_type == "ImportantNotesMiddleware":
            middlewares.append(ImportantNotesMiddleware())
        elif middleware_type == "ContextEditingMiddleware":
            edits = []
            for edit_config in config.get("edits", []):
                edit_type = edit_config.get("type")
                if edit_type == "LongChainWakeUp":
                    edits.append(LongChainWakeUp(
                        max_consecutive_counts=edit_config.get("max_consecutive_counts", 20),
                        important_tool_name=edit_config.get("important_tool_name", "write_important_notes"),
                        exclude_tools=edit_config.get("exclude_tools", ["write_todos"])
                    ))
                elif edit_type == "ClearToolUsesEdit":
                    edits.append(ClearToolUsesEdit(
                        trigger=edit_config.get("trigger", 100000),
                        keep=edit_config.get("keep", 3),
                        exclude_tools=edit_config.get("exclude_tools", []),
                        clear_tool_inputs=edit_config.get("clear_tool_inputs", False)
                    ))
            middlewares.append(ContextEditingMiddleware(edits=edits))
            
    return middlewares


def create_subagents(subagent_configs: List[Dict[str, Any]], tools_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create subagents based on configuration.
    
    Args:
        subagent_configs (list): List of subagent configurations
        tools_map (dict): Map of tool names to actual tool objects
        
    Returns:
        list: List of configured subagent dictionaries
    """
    subagents = []
    
    for config in subagent_configs:
        # Resolve tools
        resolved_tools = []
        for tool_name in config.get("tools", []):
            if tool_name in tools_map:
                resolved_tools.append(tools_map[tool_name])
        
        # Create middleware
        middleware = create_middleware_list(config.get("middleware", []))
        
        subagent = {
            "name": config["name"],
            "description": config["description"],
            "system_prompt": config["system_prompt"],
            "tools": resolved_tools,
            "model": main_model,  # Simplified - could be configurable
            "middleware": middleware
        }
        
        subagents.append(subagent)
        
    return subagents


def compose_agent_from_yaml(config_path: str | None = None) -> Any:
    """
    Compose an agent from YAML configuration.
    
    Args:
        config_path (str): Path to the YAML configuration file
        tools_map (dict): Map of tool names to actual tool objects
        
    Returns:
        Configured agent
    """
    config = load_config(config_path)
    
    # Create tools map
    tools_map = {
        "curl": curl,
        "execute_python_code_command": execute_python_code_command,
        "get_kali_openapi_spec": get_kali_openapi_spec
    }
    
    # Resolve main agent tools
    main_agent_tools = []
    for tool_name in config.get("tools", []):
        if tool_name in tools_map:
            main_agent_tools.append(tools_map[tool_name])
    
    # Create middleware
    middleware = create_middleware_list(config.get("middleware", []))
    
    # Create subagents
    subagents = create_subagents(config.get("subagents", []), tools_map)
    
    # Create backend
    def backend_factory(runtime):
        return make_backend(runtime, config.get("filesystem_backend", {}))
    
    # Create the agent
    agent = create_deep_agent(
        model=main_model,
        system_prompt=config["system_prompt"],
        response_format=FlagResponse,
        tools=main_agent_tools,
        subagents=subagents,
        middleware=middleware,
        backend=backend_factory
    )
    
    return agent


ctf_deepagents = compose_agent_from_yaml("ctf_deepagents.yaml")
