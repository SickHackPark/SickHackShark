from langchain.agents.middleware.context_editing import ContextEdit, TokenCounter

from typing import List, Tuple, Sequence
import re
from langchain_core.messages import ToolMessage, HumanMessage, AnyMessage


class LongChainWakeUp(ContextEdit):
    """"""

    def __init__(
            self,
            max_consecutive_counts: int = 20,
            important_tool_name: str = "write_important_notes",
            exclude_tools: Sequence[str] = ()
    ) -> None:
        """Initialize the limit tool usage edit.

        Args:
            max_consecutive_counts: Maximum number of consecutive uses of the same tool
            important_tool_name: Name of the tool to use for important progress
            exclude_tools: List of tool names to exclude from limiting
        """
        self.max_consecutive_counts = max_consecutive_counts
        self.important_tool_name = important_tool_name
        self.exclude_tools = set(exclude_tools)

    def apply(
            self,
            messages: list[AnyMessage],
            *,
            count_tokens: TokenCounter,
    ) -> None:
        """Apply the limit-tool-usage strategy."""
        # Get all tool messages
        tool_messages = []
        for idx, message in enumerate(messages):
            if isinstance(message, ToolMessage) and message.name not in self.exclude_tools:
                tool_messages.append((idx, message))

        # If we have less than x tool messages, no need to intervene
        if len(tool_messages) < self.max_consecutive_counts:
            return

        # Get the last x tool messages
        last_x_tool_messages = tool_messages[-self.max_consecutive_counts:]

        is_contained_important_tool_name = False

        for _, message in last_x_tool_messages:
            tool_name = message.name or "unknown_tool"

            # Check if write_important_notes is in the last x tool messages
            if tool_name == self.important_tool_name:
                is_contained_important_tool_name = True
        if not is_contained_important_tool_name:
            self._handle_message(messages, last_x_tool_messages)

    def _handle_message(self, messages: list, last_x_tool_messages) -> None:
        # Get the index of the last tool message
        last_tool_index, _ = last_x_tool_messages[-1]

        # Remove previous behavior calibration messages
        messages_to_remove = []
        for idx, message in enumerate(messages):
            if isinstance(message, HumanMessage) and isinstance(message.content,
                                                                str) and "======行为校准======" in message.content:
                messages_to_remove.append(idx)

        # Remove messages in reverse order to maintain index integrity
        for idx in reversed(messages_to_remove):
            messages.pop(idx)

        # Adjust last_tool_index if messages were removed
        removed_count_before_last_tool = sum(1 for idx in messages_to_remove if idx <= last_tool_index)
        last_tool_index -= removed_count_before_last_tool

        # Process human messages - handle both string and list content
        list_human_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                if isinstance(message.content, list):
                    # If content is a list, join all string elements
                    content_parts = [str(part) for part in message.content if isinstance(part, str)]
                    list_human_messages.append("".join(content_parts))
                else:
                    # If content is a string, use it directly
                    list_human_messages.append(str(message.content))

        first_human_message = str(list_human_messages[0])

        # Extract flag-like patterns from message history
        flag_patterns = []
        flag_regex = re.compile(r'(flag\{.*?\}|FLAG\{.*?\}|Flag\{.*?\})')
        for message in messages:
            if hasattr(message, 'content') and message.content:
                content_str = ""
                if isinstance(message.content, str):
                    content_str = message.content
                elif isinstance(message.content, list):
                    # Join all string elements in the list
                    content_parts = [str(part) for part in message.content if isinstance(part, str)]
                    content_str = "".join(content_parts)

                matches = flag_regex.findall(content_str)
                if matches:
                    flag_patterns.extend(matches)
        flags_text = ""
        if flag_patterns:
            flags_text_catch = "\n".join(flag_patterns)
            flags_text = f"\n\n# 匹配到的flag内容\n{flags_text_catch}\n- 请检查上面列出的flag匹配内容，确认是否已经获取到了flag"

        # Inject a human message right after the last tool message
        list_important_notes = [message.content for message in messages if
                                hasattr(message, 'name') and message.name == "write_important_notes"]
        all_important_notes = "\n".join(list_important_notes)
        human_message = HumanMessage(
            content=(
                    """---

# 漏洞测试技巧
以下是常见Web漏洞的通用挖掘技巧，侧重如何发现和利用：

1. IDOR（不安全的直接对象引用）：
   - 测试所有ID类参数（如`?id=1`、`/user/123`），尝试修改为其他值（如递增、递减、其他用户ID）。
   - 检查Cookie、Headers中的ID参数，Base64解码后测试。
   - 注意间接IDOR：操作后影响其他位置的数据（如修改自身资料后查看他人数据）。

2. XSS（跨站脚本）：
   - 测试所有用户输入点（如表单、URL参数、Cookie），注入简单Payload（如`<script>alert('XSS')</script>`）。
   - 如果过滤存在，尝试绕过：大小写变形、使用事件处理器（如`onerror`）、编码（如HTML实体）、替换标签（如`<img src=x onerror=alert('XSS')>`）。
   - 先尝试构造弹窗可不可以在响应中获取flag内容，不行再尝试其他获取flag的方法
   - 检查响应HTML，确认Payload是否被执行；如果弹窗被阻止，尝试其他方式获取flag（如读取DOM内容）。

3. SSTI（服务器模板注入）：
   - 在输入点注入模板语法（如Jinja2的`{{ 7*7 }}`、Django的`{% debug %}`），观察响应是否执行。
   - 如果盲注，使用延迟命令（如`{{ ''.__class__.__mro__[1].__subclasses__() }}`）或错误回显判断。
   - 利用SSTI执行系统命令读取文件（如`{{ config.items() }}`或`{{ ''.__class__.__mro__[1].__subclasses__()[40]('/flag.txt').read() }}`）。
   - SSTI获取flag方法可以先尝试简单的`{{flag}}`，不生效再尝试其他方法

4. SQL注入（SQLi）：
   - 测试参数使用单引号、双引号，观察错误消息。
   - 如果错误被屏蔽，尝试盲注：基于布尔（如`' AND 1=1 --`）或时间延迟（如`' AND SLEEP(5) --`）。
   - 绕过白名单：使用编码（如Base64）、注释（如`//`）、大小写混合。

5. 命令注入：
   - 在输入点注入系统命令分隔符（如`;`、`&&`、`|`），执行`whoami`或`cat /flag.txt`。
   - 如果过滤空格，使用替代符（如`${IFS}`、`%20`）；如果过滤关键词，使用编码或通配符。

6. 文件上传漏洞：
   - 上传恶意文件（如WebShell的PHP文件），绕过扩展名检查（如`.php5`、`.phtml`）、MIME类型检查（如修改Content-Type）。
   - 如果只允许图像，尝试图片头伪造（如GIF89a+PHP代码）。
   - 上传后访问文件路径，执行命令读取flag。

7. SSRF（服务端请求伪造）：
   - 测试URL参数，尝试访问内部服务（如`http://localhost`、`file:///etc/passwd`）。
   - 绕过黑名单：使用域名重定向、IPv6地址、URL编码。

8. XXE（XML外部实体注入）：
   - 在XML输入中注入外部实体（如`<!ENTITY xxe SYSTEM "file:///flag.txt">`），读取文件。
   - 如果禁用外部实体，尝试使用参数实体或HTTP外带数据。

9. 反序列化漏洞：
   - 检查Cookie、POST数据中的序列化对象（如PHP的`serialize()`、Python的`pickle`）。
   - 构造恶意序列化数据执行系统命令（如Python的`__reduce__`方法）。

10. JWT漏洞：
    - 解码JWT Token，检查是否未签名（`alg: none`）或使用弱密钥。
    - 篡改Payload（如修改用户角色为admin），重新签名或直接发送。

11. 路径遍历/LFI：
    - 测试文件参数（如`?file=../../flag.txt`），使用编码（如`..%2f`）或空字节绕过。
    - 利用PHP包装器读取源码（如`php://filter/convert.base64-encode/resource=index.php`）。

12. 默认凭证与信息泄露：
    - 尝试常见默认密码（如`admin:admin`）、检查robots.txt、.git目录、备份文件。
    - 分析错误消息，可能泄露路径或数据库信息。

13. 已知第三方漏洞利用：
    - 涉及知名CMS：WordPress、Drupal、Joomla、Magento、CakePHP、Laravel、Symfony、Zend、Phalcon、Yii等。
    - 使用kali里的searchsploit搜索漏洞已知poc，找到已知的漏洞利用方法。
    - 利用kali工具进行漏洞利用，并利用漏洞获取flag。
---

# flag获取技巧
- 常见flag位置：
  - 文件系统：`/flag.txt`、`/app/flag`、`/tmp/flag`。
  - 数据库：通过SQL注入查询`flag`表。
  - 环境变量：通过命令注入执行`env`。
  - HTTP响应：XSS弹窗内容、错误消息、静态资源注释。
- 利用漏洞读取flag：
  - 文件读取：使用LFI、XXE、SSTI、命令注入。
  - 命令执行：通过SQLi、SSTI、命令注入、反序列化执行`cat /flag.txt`。
  - 越权访问：通过IDOR或JWT篡改访问管理员界面，获取flag。
- 注意：flag可能被隐藏或需要多步利用，保持耐心，结合多个漏洞。

---""" +
                    f"======行为校准======\n# 任务信息\n {first_human_message}\n\n# 当前重要笔记汇总\n{all_important_notes}\n\n# 要求\n" +
                    f"- 请先使用 '{self.important_tool_name}' 工具总结当前进度与发现，" +
                    f"再继续调用更多工具。\n- 对于测试成功的漏洞payload，需要使用curl -v 采样一下完整的请求和响应信息\n{flags_text}" + """

## 文件说明:
### 漏洞payload及绕过技术资料库 /root/SickHack/knowledge_base/PayloadsAllTheThings
一份实用的Web应用安全与渗透测试/CTF的payload及绕过技术资料库，用于获取有用的payload及绕过技术。

### Web安全学习资料库 /root/SickHack/knowledge_base/web-security
本目录包含了从PortSwigger Web Security Academy收集的各类Web安全漏洞学习材料和实验指南，旨在为Web渗透测试人员提供全面的技术参考。

### 一系列关于漏洞挖掘的实用指南、方法论和资源 /root/SickHack/knowledge_base/HowToHunt
本目录包含了一系列关于漏洞挖掘的实用指南、方法论和资源 /root/SickHack/knowledge_base/HowToHunt

### 阅读文件的方法

使用`ls`工具获取正在测试的漏洞相关的文件 -> 选择尽可能多的相关待阅读的文件列表 -> 使用`read_file`工具获取文件内容

### 阅读文件的时机

漏洞测试失败时，去/root/SickHack/knowledge_base 阅读相关的材料（web-security + PayloadsAllTheThings + HowToHunt），再展开具体的漏洞挖掘与利用工作"""
            )
        )

        # Insert the human message after the last tool message
        messages.insert(last_tool_index + 1, human_message)