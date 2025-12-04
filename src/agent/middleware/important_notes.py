"""Planning and task management middleware for agents."""
# ruff: noqa: E501

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, Optional
import yaml

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from typing_extensions import NotRequired, TypedDict

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelCallResult,
    ModelRequest,
    ModelResponse,
)
from langchain.tools import InjectedToolCallId


class ImportantNote(TypedDict):
    """A single important note with content and category."""

    content: str
    """The content of the important note."""

    category: str
    """The category of the note."""
    
    http_requests: list[str]
    """Associated HTTP request messages list."""


class GeneralNote(ImportantNote):
    """A general note for observations that don't fit other categories."""
    pass


class VulnerabilityNote(ImportantNote):
    """A note documenting a security vulnerability."""

    vulnerability_type: str
    """The type of vulnerability found."""


class FindingNote(ImportantNote):
    """A note for key findings during assessment."""
    pass


class EvidenceNote(ImportantNote):
    """A note containing evidence supporting findings."""
    pass


class PocNote(ImportantNote):
    """A note containing proof-of-concept information."""
    pass


class RecommendationNote(ImportantNote):
    """A note containing recommendations based on findings."""
    pass


class WebsiteStructureNote(ImportantNote):
    """A note containing website structure, interface information and functionality."""
    
    url: str
    """The URL or API endpoint related to the structure."""
    
    structure_details: str
    """Details about the website structure, interfaces or functionality."""


class ExplorationNote(ImportantNote):
    """A note documenting website functionality exploration."""

    url: str
    """The URL or API endpoint explored."""


class ExploitAttemptNote(ImportantNote):
    """A note documenting vulnerability exploitation attempts."""

    url: str
    """The target URL or API endpoint."""

    vulnerability_type: str
    """The type of vulnerability being exploited."""

    attempt_result: Literal["success", "failure"]
    """The result of the exploit attempt."""

    can_be_further_exploited: bool
    """Whether the finding can be further exploited."""


class ImportantNotesState(AgentState):
    """State schema for the important notes middleware."""

    important_notes: Annotated[list[ImportantNote], lambda x, y: (x or []) + y]
    """List of important notes for tracking significant information."""


WRITE_IMPORTANT_NOTES_TOOL_DESCRIPTION = """Use this tool to record important notes during your work session. Record notes frequently - it's better to have more information than less.

## When to Use This Tool
Use this tool in these scenarios:
1. Recording key findings from security assessments
2. Saving important data or observations during penetration testing
3. Documenting steps taken during complex tasks
4. Keeping notes on vulnerabilities discovered
5. Recording important observations during assessment
6. Capturing intermediate results or thoughts
7. Recording failed attempts that might provide context later
8. Noting potential next steps or alternative approaches

## How to Use This Tool
1. Provide the content you want to record in the 'content' parameter
2. Categorize the content with the 'category' parameter
3. For exploration and exploit attempts, provide the 'url' parameter
4. For vulnerabilities and exploit attempts, provide the 'vulnerability_type' parameter
5. For exploit attempts, provide the 'attempt_result' and 'can_be_further_exploited' parameters
6. Provide the 'http_requests' parameter to associate HTTP request valuable messages with the note. Example:
request:
GET /api/users HTTP/1.1
Host: example.com

----
response:
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

......
{response body valuable information! no more than 500 words! no more than 500 words! no more than 500 words!}
......


## Note Categories and Required Fields
- general: For general observations (no additional fields required)
- vulnerability: For security vulnerabilities found (requires vulnerability_type)
- finding: For key findings during assessment (no additional fields required)
- evidence: For evidence supporting findings (no additional fields required)
- poc: For proof-of-concept information (no additional fields required)
- recommendation: For recommendations based on findings (no additional fields required)
- exploration: For website functionality exploration findings (requires url)
- website_structure: For website structure, interface information and functionality (requires url and structure_details)
- exploit_attempt: For vulnerability exploitation attempts (requires url, vulnerability_type, attempt_result, can_be_further_exploited)"""


IMPORTANT_NOTES_SYSTEM_PROMPT = """## `write_important_notes`

You have access to a tool for managing important notes during your work:

`write_important_notes`: Use this tool frequently to record new important information.

Use this tool to document significant findings, observations, or data that might be useful later.
You should record notes more frequently than you might initially think - it's better to have too many notes than too few. 
Record notes when:
- You want to record website_structure information or website functionality or interface information 
- You complete any meaningful step in your task
- You discover new information
- You make decisions about your approach
- You encounter obstacles or challenges
- You find information that might impact other areas of the assessment
- You want to remember details about what you've done
- You want to keep track of important data or observations
- You want to document your progress

If you're unsure whether something is worth recording, err on the side of recording it.

## Important Notes Data Structures

Different types of notes have different structures and fields. Here are the available note types and their fields:

### ImportantNote (Base Type)
- content (str): The content of the important note
- category (str): The category of the note
- http_requests (list[str]): Associated HTTP request valuable messages list. Example:
request:
GET /api/users HTTP/1.1
Host: example.com

----
response:
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

......
{response body valuable information! no more than 500 words! no more than 500 words! no more than 500 words!}
......

### GeneralNote
Inherits all fields from ImportantNote. Used for general observations.

### VulnerabilityNote
Inherits all fields from ImportantNote plus:
- vulnerability_type (str): The type of vulnerability found

### FindingNote
Inherits all fields from ImportantNote. Used for key findings during assessment.

### EvidenceNote
Inherits all fields from ImportantNote. Used for evidence supporting findings.

### PocNote
Inherits all fields from ImportantNote. Used for proof-of-concept information.

### RecommendationNote
Inherits all fields from ImportantNote. Used for recommendations based on findings.

### WebsiteStructureNote
Inherits all fields from ImportantNote plus:
- url (str): The URL or API endpoint related to the structure
- structure_details (str): Details about the website structure, interfaces or functionality

### ExplorationNote
Inherits all fields from ImportantNote plus:
- url (str): The URL or API endpoint explored

### ExploitAttemptNote
Inherits all fields from ImportantNote plus:
- url (str): The target URL or API endpoint
- vulnerability_type (str): The type of vulnerability being exploited
- attempt_result (Literal["success", "failure"]): The result of the exploit attempt
- can_be_further_exploited (bool): Whether the finding can be further exploited"""


def _add_note(notes, new_note):
    """Helper function to add a new note to the list of notes."""
    return (notes or []) + [new_note]


@tool(description=WRITE_IMPORTANT_NOTES_TOOL_DESCRIPTION)
def write_important_notes(
        http_requests: list[str],
        content: str = "",
        category: str = "general",
        url: str = "",
        structure_details: str = "",
        vulnerability_type: str = "",
        attempt_result: Literal["success", "failure", ""] = "",
        can_be_further_exploited: bool = False,
        tool_call_id: Annotated[str, InjectedToolCallId] = None,
        important_notes: Optional[list[ImportantNote]] = None
) -> Command:
    """Record important notes."""
    # Validate required fields based on category
    try:
        if category == "exploit_attempt":
            if not url:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'url' is required for exploit_attempt category.", tool_call_id=tool_call_id)],
                    }
                )
            if not vulnerability_type:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'vulnerability_type' is required for exploit_attempt category.", tool_call_id=tool_call_id)],
                    }
                )
            if not attempt_result:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'attempt_result' is required for exploit_attempt category.", tool_call_id=tool_call_id)],
                    }
                )
        elif category == "exploration":
            if not url:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'url' is required for exploration category.", tool_call_id=tool_call_id)],
                    }
                )
        elif category == "vulnerability":
            if not vulnerability_type:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'vulnerability_type' is required for vulnerability category.", tool_call_id=tool_call_id)],
                    }
                )
        elif category == "website_structure":
            if not url:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'url' is required for website_structure category.", tool_call_id=tool_call_id)],
                    }
                )
            if not structure_details:
                return Command(
                    update={
                        "messages": [ToolMessage("Error: 'structure_details' is required for website_structure category.", tool_call_id=tool_call_id)],
                    }
                )

        # Create the appropriate note type based on category
        new_note = None
        if category == "exploit_attempt":
            new_note = ExploitAttemptNote(
                content=content,
                category=category,
                url=url,
                vulnerability_type=vulnerability_type,
                attempt_result=attempt_result,
                can_be_further_exploited=can_be_further_exploited,
                http_requests=http_requests
            )
        elif category == "exploration":
            new_note = ExplorationNote(
                content=content,
                category=category,
                url=url,
                http_requests=http_requests
            )
        elif category == "vulnerability":
            new_note = VulnerabilityNote(
                content=content,
                category=category,
                vulnerability_type=vulnerability_type,
                http_requests=http_requests
            )
        elif category == "website_structure":
            new_note = WebsiteStructureNote(
                content=content,
                category=category,
                url=url,
                structure_details=structure_details,
                http_requests=http_requests
            )
        else:
            # For other categories, use the base ImportantNote type
            new_note = ImportantNote(content=content, category=category, http_requests=http_requests)

        def create_command_with_notes(notes):
            updated_notes = _add_note(notes, new_note)
            if updated_notes:
                notes_yaml = yaml.dump(updated_notes, allow_unicode=True, sort_keys=False)
                message_content = f"Current important notes list: {notes_yaml}"
            else:
                message_content = "No important notes found."

            return Command(
                update={
                    "important_notes": updated_notes,
                    "messages": [
                        ToolMessage(message_content, tool_call_id=tool_call_id)],
                }
            )

        return create_command_with_notes(important_notes)
    except Exception as e:
        return Command(
            update={
                "messages": [ToolMessage(f"Error recording important notes: {str(e)}", tool_call_id=tool_call_id)],
            }
        )


class ImportantNotesMiddleware(AgentMiddleware):
    """Middleware that provides important notes management capabilities to agents.

    This middleware adds a tool that allows agents to record and review important
    information during their work. It's designed to help agents keep track of
    significant findings, observations, or data that might be useful later.

    The middleware automatically injects system prompts that guide the agent on when
    and how to use the important notes functionality effectively.

    Args:
        tool_description: Custom description for the write_important_notes tool.
            If not provided, uses the default `WRITE_IMPORTANT_NOTES_TOOL_DESCRIPTION`.
        system_prompt: Custom system prompt to guide the agent on using the important notes tool.
            If not provided, uses the default `IMPORTANT_NOTES_SYSTEM_PROMPT`.
    """

    state_schema = ImportantNotesState

    def __init__(
            self,
            *,
            tool_description: str = WRITE_IMPORTANT_NOTES_TOOL_DESCRIPTION,
            system_prompt: str = IMPORTANT_NOTES_SYSTEM_PROMPT,
    ) -> None:
        """Initialize the ImportantNotesMiddleware with optional custom descriptions.

        Args:
            tool_description: Custom description for the write_important_notes tool.
            system_prompt: Custom system prompt to guide the agent on using the important notes tool.
        """
        super().__init__()
        self.tool_description = tool_description
        self.system_prompt = system_prompt

        # Dynamically create the tool with the custom description
        @tool(description=self.tool_description)
        def write_important_notes(
                http_requests: list[str],
                content: str = "",
                category: str = "general",
                url: str = "",
                structure_details: str = "",
                vulnerability_type: str = "",
                attempt_result: Literal["success", "failure", ""] = "",
                can_be_further_exploited: bool = False,
                tool_call_id: Annotated[str, InjectedToolCallId] = None,
                important_notes: Optional[list[ImportantNote]] = None
        ) -> Command:
            """Record important notes."""
            try:
                # Validate required fields based on category
                if category == "exploit_attempt":
                    if not url:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'url' is required for exploit_attempt category.", tool_call_id=tool_call_id)],
                            }
                        )
                    if not vulnerability_type:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'vulnerability_type' is required for exploit_attempt category.", tool_call_id=tool_call_id)],
                            }
                        )
                    if not attempt_result:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'attempt_result' is required for exploit_attempt category.", tool_call_id=tool_call_id)],
                            }
                        )
                elif category == "exploration":
                    if not url:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'url' is required for exploration category.", tool_call_id=tool_call_id)],
                            }
                        )
                elif category == "vulnerability":
                    if not vulnerability_type:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'vulnerability_type' is required for vulnerability category.", tool_call_id=tool_call_id)],
                            }
                        )
                elif category == "website_structure":
                    if not url:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'url' is required for website_structure category.", tool_call_id=tool_call_id)],
                            }
                        )
                    if not structure_details:
                        return Command(
                            update={
                                "messages": [ToolMessage("Error: 'structure_details' is required for website_structure category.", tool_call_id=tool_call_id)],
                            }
                        )

                # Create the appropriate note type based on category
                new_note = None
                if category == "exploit_attempt":
                    new_note = ExploitAttemptNote(
                        content=content,
                        category=category,
                        url=url,
                        vulnerability_type=vulnerability_type,
                        attempt_result=attempt_result,
                        can_be_further_exploited=can_be_further_exploited,
                        http_requests=http_requests
                    )
                elif category == "exploration":
                    new_note = ExplorationNote(
                        content=content,
                        category=category,
                        url=url,
                        http_requests=http_requests
                    )
                elif category == "vulnerability":
                    new_note = VulnerabilityNote(
                        content=content,
                        category=category,
                        vulnerability_type=vulnerability_type,
                        http_requests=http_requests
                    )
                elif category == "website_structure":
                    new_note = WebsiteStructureNote(
                        content=content,
                        category=category,
                        url=url,
                        structure_details=structure_details,
                        http_requests=http_requests
                    )
                else:
                    # For other categories, use the base ImportantNote type
                    new_note = ImportantNote(content=content, category=category, http_requests=http_requests)

                def create_command_with_notes(notes):
                    try:
                        updated_notes = _add_note(notes, new_note)
                        if updated_notes:
                            notes_yaml = yaml.dump(updated_notes, allow_unicode=True, sort_keys=False)
                            message_content = f"Current important notes list: {notes_yaml}"
                        else:
                            message_content = "No important notes found."

                        return Command(
                            update={
                                "important_notes": updated_notes,
                                "messages": [
                                    ToolMessage(message_content, tool_call_id=tool_call_id)],
                            }
                        )
                    except Exception as e:
                        return Command(
                            update={
                                "messages": [ToolMessage(f"Error creating command with notes: {str(e)}", tool_call_id=tool_call_id)],
                            }
                        )

                return create_command_with_notes(important_notes)
            except Exception as e:
                return Command(
                    update={
                        "messages": [ToolMessage(f"Error recording important notes: {str(e)}", tool_call_id=tool_call_id)],
                    }
                )
        self.tools = [write_important_notes]

    def wrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        """Update the system prompt to include information about the important notes tool."""
        request.system_prompt = (
            request.system_prompt + "\n\n" + self.system_prompt
            if request.system_prompt
            else self.system_prompt
        )
        return handler(request)

    async def awrap_model_call(
            self,
            request: ModelRequest,
            handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Update the system prompt to include information about the important notes tool (async version)."""
        request.system_prompt = (
            request.system_prompt + "\n\n" + self.system_prompt
            if request.system_prompt
            else self.system_prompt
        )
        return await handler(request)