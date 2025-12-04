from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import (
    AIMessage
)


def count_tokens(text: str) -> int:
    """Count the number of tokens in a string"""
    return count_tokens_approximately([AIMessage(text)])
