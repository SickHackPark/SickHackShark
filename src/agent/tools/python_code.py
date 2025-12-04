import os
from langchain_core.tools import tool
import httpx
from dotenv import load_dotenv
from agent.common.utils import count_tokens

load_dotenv(os.getenv("ENV_FILE_PATH"))


@tool
def execute_python_code_command(command: str) -> str:
    """Execute a complete python command
    The complete python command to execute (e.g., python -c 'print("hello")'
- 记得多使用`execute_python_code_command`做python代码执行，python代码执行输出只显示关键信息（比如是否期匹配到想要的内容，网页内容等）
- 使用`execute_python_code_command`做python代码执行批量http请求，比如多路径fuzz，多payload测试
- 使用requests库做请求时，请求超时设置为180s，示例代码requests.get(url, timeout=180)

    Args:
        command: The complete python command to execute (e.g., python -c "print(\"hello\")")

    Returns:
        The output of the executed command
    """
    try:
        # Prepare the request to the local API endpoint
        api_url = os.getenv("KALI_API_BASE_URL") + "api/command"
        if not command.lstrip().startswith("python"):
            return 'Error: The command must start with "python -c ". (e.g., python -c \'print("hello")\')'
        # Create the payload for our local API
        payload = {
            "command": command
        }

        # Send the request to our local API endpoint
        response = httpx.post(api_url, json=payload, timeout=180)
        result = response.json()
        response_text = f'{result["stderr"]}\n\n{result["stdout"]}'
        # Check token count and truncate if necessary
        token_count = count_tokens(response_text)
        if token_count > 10000:
            # Return first 5000 characters plus ellipsis
            return response_text[
                   :5000] + "\n\n... (response content too large, truncated)\n\nConsider using `execute_python_code_command` tool to extract valuable content"
        return response_text
    except Exception as e:
        return f"Error executing python command: {str(e)}"
