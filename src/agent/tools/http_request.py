import os
import re
from langchain_core.tools import tool
import httpx
from dotenv import load_dotenv

from agent.common.utils import count_tokens

load_dotenv(os.getenv("ENV_FILE_PATH"))


@tool
def curl(command: str) -> str:
    """Execute a complete curl command. Always use the -v parameter to get detailed information.
- 在需要完整采样请求和响应信息的情况下需要使用`curl`工具
- 对于测试成功的漏洞payload，需要使用curl -v 采样一下完整的请求和响应信息

    Args:
        command: The complete curl command to execute (e.g., "curl -v -X GET http://example.com")

    Returns:
        The response from the curl request
    """
    try:
        # Prepare the request to the local API endpoint
        api_url = os.getenv("KALI_API_BASE_URL") + "api/command"

        # Create the payload for our local API
        payload = {
            "command": command
        }

        # Send the request to our local API endpoint
        response = httpx.post(api_url, json=payload, timeout=180)
        result = response.json()
        response_text = f'{result["stderr"]}\n\n{result["stdout"]}'
        list_flag = re.findall(r'(flag\{.*?\}|FLAG\{.*?\}|Flag\{.*?\})', str(result))
        if list_flag:
            flag = "\n".join(list_flag)
            response_text = f"# 重要发现！\n 在响应中发现疑似flag：{flag}，请重视！并验证是否为正确的flag！\n\n # curl命令结果返回：\n" + response_text
        # Check token count and truncate if necessary
        token_count = count_tokens(response_text)
        if token_count > 10000:
            # Return first 5000 characters plus ellipsis
            return response_text[
                   :5000] + "\n\n... (response content too large, truncated)\n\nConsider using `execute_python_code_command` tool to extract valuable content"
        return response_text
    except Exception as e:
        return f"Error executing curl: {str(e)}"