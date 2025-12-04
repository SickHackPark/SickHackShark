import os
from langchain_core.tools import tool
import httpx
from dotenv import load_dotenv

load_dotenv(os.getenv("ENV_FILE_PATH"))


@tool
def get_kali_openapi_spec() -> str:
    """Get the OpenAPI specification from the Kali Linux Tools API Server
    Kali Linux Tools API Server is a tool that provides an OpenAPI specification for the Kali Linux tools.

    Returns:
        The OpenAPI specification as a JSON string
    """
    try:
        api_url = os.getenv("KALI_API_BASE_URL") + "openapi.json"
        response = httpx.get(api_url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error fetching OpenAPI spec: {str(e)}"