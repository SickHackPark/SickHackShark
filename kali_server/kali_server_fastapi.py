#!/usr/bin/env python3

# This script connect the MCP AI agent to Kali Linux terminal and API Server.
# Rewritten with FastAPI

# some of the code here was inspired from https://github.com/whit3rabbit0/project_astro , be sure to check them out

import asyncio
import argparse
import json
import logging
import os
import subprocess
import sys
import traceback
import threading
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_PORT = int(os.environ.get("API_PORT", 5000))
DEBUG_MODE = os.environ.get("DEBUG_MODE", "0").lower() in ("1", "true", "yes", "y")
COMMAND_TIMEOUT = 3600  # 5 minutes default timeout

app = FastAPI(title="Kali Linux Tools API Server", 
              description="API Server for executing Kali Linux tools",
              version="1.0.0")

# Pydantic models for API parameters
class CommandRequest(BaseModel):
    command: str

class SQLMapRequest(BaseModel):
    url: str
    data: Optional[str] = ""
    additional_args: Optional[str] = ""

class MetasploitRequest(BaseModel):
    module: str
    options: Optional[Dict[str, Any]] = {}

class HydraRequest(BaseModel):
    target: str
    service: str
    username: Optional[str] = ""
    username_file: Optional[str] = ""
    password: Optional[str] = ""
    password_file: Optional[str] = ""
    additional_args: Optional[str] = ""

class WPScanRequest(BaseModel):
    url: str
    additional_args: Optional[str] = ""

class Enum4LinuxRequest(BaseModel):
    target: str
    additional_args: Optional[str] = "-a"

class CurlRequest(BaseModel):
    url: str
    additional_args: Optional[str] = ""


class CurlDownloadRequest(BaseModel):
    url: str
    output_file: Optional[str] = None
    additional_args: Optional[str] = ""


class CommandExecutor:
    """Class to handle command execution with better timeout management"""
    
    def __init__(self, command: str, timeout: int = COMMAND_TIMEOUT):
        self.command = command
        self.timeout = timeout
        self.process = None
        self.stdout_data = ""
        self.stderr_data = ""
        self.return_code = None
        self.timed_out = False
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the command and handle timeout gracefully"""
        logger.info(f"Executing command: {self.command}")
        
        try:
            # Use asyncio subprocess for non-blocking execution
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Create tasks for reading stdout and stderr
            stdout_task = asyncio.create_task(self.process.stdout.read())
            stderr_task = asyncio.create_task(self.process.stderr.read())
            
            # Wait for the process to complete or timeout
            try:
                await asyncio.wait_for(self.process.wait(), timeout=self.timeout)
            except asyncio.TimeoutError:
                # Process timed out
                self.timed_out = True
                logger.warning(f"Command timed out after {self.timeout} seconds. Terminating process.")
                
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning("Process not responding to termination. Killing.")
                    self.process.kill()
                    await asyncio.wait_for(self.process.wait(), timeout=1)
                except ProcessLookupError:
                    # Process already finished
                    pass
                
                # Update final output
                self.return_code = -1
            
            # Get results from tasks
            try:
                stdout_data = await stdout_task
                stderr_data = await stderr_task
                
                self.stdout_data = stdout_data.decode('utf-8', errors='replace')
                self.stderr_data = stderr_data.decode('utf-8', errors='replace')
            except Exception as e:
                logger.error(f"Error reading process output: {str(e)}")
                
            # Always consider it a success if we have output, even with timeout
            success = True if self.timed_out and (self.stdout_data or self.stderr_data) else (self.return_code == 0)
            
            return {
                "stdout": self.stdout_data,
                "stderr": self.stderr_data,
                "return_code": self.return_code,
                "success": success,
                "timed_out": self.timed_out,
                "partial_results": self.timed_out and (self.stdout_data or self.stderr_data)
            }
        
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "stdout": self.stdout_data,
                "stderr": f"Error executing command: {str(e)}\n{self.stderr_data}",
                "return_code": -1,
                "success": False,
                "timed_out": False,
                "partial_results": bool(self.stdout_data or self.stderr_data)
            }


async def execute_command(command: str) -> Dict[str, Any]:
    """
    Execute a shell command and return the result
    
    Args:
        command: The command to execute
        
    Returns:
        A dictionary containing the stdout, stderr, and return code
    """
    # 特殊处理可能导致二进制输出的命令
    binary_output_commands = ['curl ', 'wget ', 'cat ', 'hexdump ', 'xxd ']
    if any(cmd in command for cmd in binary_output_commands) and '--output' not in command and '>' not in command:
        # 添加参数避免二进制数据污染终端
        if command.startswith('curl'):
            # 检查是否是明显的二进制文件下载
            binary_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.pdf', '.zip', '.tar', '.exe']
            if any(ext in command for ext in binary_extensions):
                # 对于二进制文件下载，静默模式并丢弃输出
                command = command.replace('curl ', 'curl --silent --output /dev/null ', 1) + ' && echo "File downloaded successfully (output discarded to prevent terminal corruption)"'
            else:
                # 对于其他 curl 请求，使用 --silent 减少冗余输出
                command = command.replace('curl ', 'curl --silent --output - ', 1)
    
    executor = CommandExecutor(command)
    return await executor.execute()


@app.post("/api/command")
async def generic_command(request: CommandRequest):
    """Execute any command provided in the request."""
    try:
        command = request.command
        
        if not command:
            logger.warning("Command endpoint called without command parameter")
            raise HTTPException(status_code=400, detail="Command parameter is required")
        
        # 对可能导致问题的命令进行特殊处理
        # 特别是 curl 命令，如果可能产生二进制输出则需要处理
        if command.strip().startswith('curl') and '--output' not in command and '>' not in command:
            # 检查是否是下载图片或其他二进制文件的请求
            if any(ext in command for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                # 对于明显是下载图像文件的命令，我们将其重定向为静默模式
                command = command.replace('curl ', 'curl --silent --output /dev/null ', 1) + ' 2>&1'
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in command endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/nmap")
async def nmap(request: Request):
    """Execute nmap scan with the provided parameters."""
    try:
        params = await request.json()
        target = params.get("target", "")
        scan_type = params.get("scan_type", "-sCV")
        ports = params.get("ports", "")
        additional_args = params.get("additional_args", "-T4 -Pn")

        if not target:
            logger.warning("Nmap called without target parameter")
            raise HTTPException(status_code=400, detail="Target parameter is required")

        command = f"nmap {scan_type}"

        if ports:
            command += f" -p {ports}"

        if additional_args:
            # Basic validation for additional args - more sophisticated validation would be better
            command += f" {additional_args}"

        command += f" {target}"

        result = execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in nmap endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/gobuster")
async def gobuster(request: Request):
    """Execute gobuster with the provided parameters."""
    try:
        params = await request.json()
        url = params.get("url", "")
        mode = params.get("mode", "dir")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        additional_args = params.get("additional_args", "")

        if not url:
            logger.warning("Gobuster called without URL parameter")
            raise HTTPException(status_code=400, detail="URL parameter is required")

        # Validate mode
        if mode not in ["dir", "dns", "fuzz", "vhost"]:
            logger.warning(f"Invalid gobuster mode: {mode}")
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}. Must be one of: dir, dns, fuzz, vhost")

        command = f"gobuster {mode} -u {url} -w {wordlist}"

        if additional_args:
            command += f" {additional_args}"

        result = execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in gobuster endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/dirb")
async def dirb(request: Request):
    """Execute dirb with the provided parameters."""
    try:
        params = await request.json()
        url = params.get("url", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        additional_args = params.get("additional_args", "")

        if not url:
            logger.warning("Dirb called without URL parameter")
            raise HTTPException(status_code=400, detail="URL parameter is required")

        command = f"dirb {url} {wordlist}"

        if additional_args:
            command += f" {additional_args}"

        result = execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in dirb endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/nikto")
async def nikto(request: Request):
    """Execute nikto with the provided parameters."""
    try:
        params = await request.json()
        target = params.get("target", "")
        additional_args = params.get("additional_args", "")

        if not target:
            logger.warning("Nikto called without target parameter")
            raise HTTPException(status_code=400, detail="Target parameter is required")

        command = f"nikto -h {target}"

        if additional_args:
            command += f" {additional_args}"

        result = execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in nikto endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/sqlmap")
async def sqlmap(request: SQLMapRequest):
    """Execute sqlmap with the provided parameters."""
    try:
        url = request.url
        data = request.data
        additional_args = request.additional_args
        
        if not url:
            logger.warning("SQLMap called without URL parameter")
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        command = f"sqlmap -u {url} --batch"
        
        if data:
            command += f" --data=\"{data}\""
        
        if additional_args:
            command += f" {additional_args}"
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in sqlmap endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/metasploit")
async def metasploit(request: MetasploitRequest):
    """Execute metasploit module with the provided parameters."""
    try:
        module = request.module
        options = request.options or {}
        
        if not module:
            logger.warning("Metasploit called without module parameter")
            raise HTTPException(status_code=400, detail="Module parameter is required")
        
        # Format options for Metasploit
        options_str = ""
        for key, value in options.items():
            options_str += f" {key}={value}"
        
        # Create an MSF resource script
        resource_content = f"use {module}\n"
        for key, value in options.items():
            resource_content += f"set {key} {value}\n"
        resource_content += "exploit\n"
        
        # Save resource script to a temporary file
        resource_file = "/tmp/mcp_msf_resource.rc"
        with open(resource_file, "w") as f:
            f.write(resource_content)
        
        command = f"msfconsole -q -r {resource_file}"
        result = await execute_command(command)
        
        # Clean up the temporary file
        try:
            os.remove(resource_file)
        except Exception as e:
            logger.warning(f"Error removing temporary resource file: {str(e)}")
        
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in metasploit endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/hydra")
async def hydra(request: HydraRequest):
    """Execute hydra with the provided parameters."""
    try:
        target = request.target
        service = request.service
        username = request.username
        username_file = request.username_file
        password = request.password
        password_file = request.password_file
        additional_args = request.additional_args
        
        if not target or not service:
            logger.warning("Hydra called without target or service parameter")
            raise HTTPException(status_code=400, detail="Target and service parameters are required")
        
        if not (username or username_file) or not (password or password_file):
            logger.warning("Hydra called without username/password parameters")
            raise HTTPException(status_code=400, detail="Username/username_file and password/password_file are required")
        
        command = f"hydra -t 4"
        
        if username:
            command += f" -l {username}"
        elif username_file:
            command += f" -L {username_file}"
        
        if password:
            command += f" -p {password}"
        elif password_file:
            command += f" -P {password_file}"
        
        if additional_args:
            command += f" {additional_args}"
        
        command += f" {target} {service}"
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in hydra endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/john")
async def john(request: Request):
    """Execute john with the provided parameters."""
    try:
        params = await request.json()
        hash_file = params.get("hash_file", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        format_type = params.get("format", "")
        additional_args = params.get("additional_args", "")

        if not hash_file:
            logger.warning("John called without hash_file parameter")
            raise HTTPException(status_code=400, detail="Hash file parameter is required")

        command = f"john"

        if format_type:
            command += f" --format={format_type}"

        if wordlist:
            command += f" --wordlist={wordlist}"

        if additional_args:
            command += f" {additional_args}"

        command += f" {hash_file}"

        result = execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in john endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/wpscan")
async def wpscan(request: WPScanRequest):
    """Execute wpscan with the provided parameters."""
    try:
        url = request.url
        additional_args = request.additional_args
        
        if not url:
            logger.warning("WPScan called without URL parameter")
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        command = f"wpscan --url {url}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in wpscan endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/enum4linux")
async def enum4linux(request: Enum4LinuxRequest):
    """Execute enum4linux with the provided parameters."""
    try:
        target = request.target
        additional_args = request.additional_args
        
        if not target:
            logger.warning("Enum4linux called without target parameter")
            raise HTTPException(status_code=400, detail="Target parameter is required")
        
        command = f"enum4linux {additional_args} {target}"
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in enum4linux endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/curl")
async def curl(request: CurlRequest):
    """Execute curl with the provided parameters."""
    try:
        url = request.url
        additional_args = request.additional_args
        
        if not url:
            logger.warning("Curl called without URL parameter")
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        command = f"curl {url}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in curl endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/api/tools/curl_download")
async def curl_download(request: CurlDownloadRequest):
    """Execute curl to download a file with proper handling."""
    try:
        url = request.url
        output_file = request.output_file
        additional_args = request.additional_args
        
        if not url:
            logger.warning("Curl download called without URL parameter")
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        # 如果没有指定输出文件，则使用 --output - 将内容输出到标准输出
        # 同时添加 --silent 来减少详细输出
        command = f"curl --silent {url}"
        
        if output_file:
            command += f" --output {output_file}"
        else:
            # 对于通过API下载的文件，强制输出到stdout
            command += " --output -"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = await execute_command(command)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in curl download endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check if essential tools are installed
    essential_tools = ["nmap", "gobuster", "dirb", "nikto", "curl"]
    tools_status = {}
    
    for tool in essential_tools:
        try:
            result = await execute_command(f"which {tool}")
            tools_status[tool] = result["success"]
        except:
            tools_status[tool] = False
    
    all_essential_tools_available = all(tools_status.values())
    
    return JSONResponse(content={
        "status": "healthy",
        "message": "Kali Linux Tools API Server is running",
        "tools_status": tools_status,
        "all_essential_tools_available": all_essential_tools_available
    })


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Kali Linux API Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, default=API_PORT, help=f"Port for the API server (default: {API_PORT})")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Set configuration from command line arguments
    if args.debug:
        DEBUG_MODE = True
        os.environ["DEBUG_MODE"] = "1"
        logger.setLevel(logging.DEBUG)
    
    if args.port != API_PORT:
        API_PORT = args.port
    
    logger.info(f"Starting Kali Linux Tools API Server on port {API_PORT}")
    uvicorn.run("kali_server_fastapi:app", host="0.0.0.0", port=API_PORT, reload=DEBUG_MODE)