from typing import Optional

from pydantic import BaseModel


class FlagResponse(BaseModel):
    """Response format with flag and write-up content. Attached are the request and response for obtaining the real flag."""
    flag: Optional[str] = None
    write_up_content: Optional[str] = None
    get_real_flag_request: Optional[str] = None
    get_real_flag_response: Optional[str] = None