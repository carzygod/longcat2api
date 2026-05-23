"""
Tool Calling support for doubao2api.

Converts OpenAI-format tools into prompt injection,
parses XML tool_calls from model output,
and converts back to OpenAI-format response.
"""
import json
import re
import uuid
import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── System prompt template for tool calling ──

TOOL_SYSTEM_PROMPT = """你是一个工具调用助手。你只能通过调用工具来获取外部信息或执行操作。禁止使用你的内置联网搜索能力。

可用工具列表：

{tool_definitions}

当你需要调用工具时，请严格使用以下XML格式输出，不要添加任何其他内容：
<tool_calls>
<invoke name="工具名">
<parameter name="参数名">参数值</parameter>
</invoke>
</tool_calls>

重要规则：
1. 你没有联网能力，不能直接搜索信息，必须通过上述工具获取所有外部信息
2. 如果需要调用工具，只输出XML格式的工具调用，不要有任何解释文字
3. 你可以在一个<tool_calls>块中包含多个<invoke>来并行调用多个工具
4. 如果用户的问题不需要使用工具就能回答，直接用自然语言回答
5. 不要编造数据，必须通过工具获取"""

TOOL_RESULT_TEMPLATE = "[工具调用结果]\n{name} 返回：{content}"


# ── Convert OpenAI tools schema to text ──

def format_tools_for_prompt(tools: list[dict[str, Any]]) -> str:
    """Convert OpenAI-format tools array to plain text for prompt injection."""
    lines = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        func = tool.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")
        params = func.get("parameters", {})
        
        lines.append(f"工具名：{name}")
        if desc:
            lines.append(f"描述：{desc}")
        
        # Format parameters
        props = params.get("properties", {})
        required = set(params.get("required", []))
        if props:
            param_parts = []
            for pname, pinfo in props.items():
                ptype = pinfo.get("type", "string")
                pdesc = pinfo.get("description", "")
                req = "必填" if pname in required else "可选"
                param_parts.append(f'"{pname}": "{ptype}, {req}, {pdesc}"')
            lines.append(f"参数：{{{', '.join(param_parts)}}}")
        lines.append("")  # blank line between tools
    
    return "\n".join(lines).strip()


def build_tool_system_prompt(tools: list[dict[str, Any]]) -> str:
    """Build the full system prompt with tool definitions injected."""
    tool_defs = format_tools_for_prompt(tools)
    return TOOL_SYSTEM_PROMPT.format(tool_definitions=tool_defs)


# ── XML Parser for tool_calls ──

# Regex patterns for parsing XML tool calls
_TOOL_CALLS_RE = re.compile(
    r"<tool_calls>\s*(.*?)\s*</tool_calls>",
    re.DOTALL,
)
_INVOKE_RE = re.compile(
    r'<invoke\s+name="([^"]+)">\s*(.*?)\s*</invoke>',
    re.DOTALL,
)
_PARAM_RE = re.compile(
    r'<parameter\s+name="([^"]+)">(.*?)</parameter>',
    re.DOTALL,
)


def parse_tool_calls_xml(text: str) -> Optional[list[dict[str, Any]]]:
    """Parse XML tool_calls from model output.
    
    Returns list of OpenAI-format tool_call dicts, or None if no tool calls found.
    """
    match = _TOOL_CALLS_RE.search(text)
    if not match:
        return None
    
    inner = match.group(1)
    tool_calls = []
    
    for invoke_match in _INVOKE_RE.finditer(inner):
        func_name = invoke_match.group(1)
        params_text = invoke_match.group(2)
        
        # Parse parameters into a dict
        arguments = {}
        for param_match in _PARAM_RE.finditer(params_text):
            param_name = param_match.group(1)
            param_value = param_match.group(2).strip()
            arguments[param_name] = param_value
        
        tool_call = {
            "id": f"call_{uuid.uuid4().hex[:24]}",
            "type": "function",
            "function": {
                "name": func_name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        }
        tool_calls.append(tool_call)
    
    return tool_calls if tool_calls else None


def is_tool_call_start(text: str) -> bool:
    """Check if accumulated text looks like the start of a tool call."""
    stripped = text.strip()
    return stripped.startswith("<tool_calls>") or stripped.startswith("<tool_call")


def has_complete_tool_calls(text: str) -> bool:
    """Check if text contains a complete <tool_calls>...</tool_calls> block."""
    return "</tool_calls>" in text


# ── Message conversion for multi-turn tool use ──

def convert_messages_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> str:
    """Convert OpenAI-format messages (including role:tool) to plain text prompt.
    
    Handles:
    - Injects tool system prompt
    - Converts role:assistant with tool_calls to XML format
    - Converts role:tool results to readable text
    """
    tool_system = build_tool_system_prompt(tools)
    parts = []
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "system":
            # Prepend user's system prompt, then our tool prompt
            if content:
                parts.append(f"[system]: {content}\n\n{tool_system}")
            continue
        
        elif role == "tool":
            # Convert tool result to readable format
            name = msg.get("name", "unknown_tool")
            parts.append(TOOL_RESULT_TEMPLATE.format(
                name=name, content=content or ""
            ))
        
        elif role == "assistant":
            # If assistant message has tool_calls, reconstruct XML
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                xml = _reconstruct_tool_calls_xml(tool_calls)
                parts.append(f"[assistant]: {xml}")
            elif content:
                parts.append(f"[assistant]: {content}")
        
        elif role == "user":
            if isinstance(content, str):
                parts.append(f"[user]: {content}")
            elif isinstance(content, list):
                # Handle multimodal content
                text_parts = [p.get("text", "") for p in content 
                             if isinstance(p, dict) and p.get("type") == "text"]
                if text_parts:
                    parts.append(f"[user]: {''.join(text_parts)}")
    
    # If no system message was found, prepend tool system prompt
    if not any(m.get("role") == "system" for m in messages):
        parts.insert(0, f"[system]: {tool_system}")
    
    return "\n\n".join(parts)


def _reconstruct_tool_calls_xml(tool_calls: list[dict[str, Any]]) -> str:
    """Reconstruct XML from OpenAI-format tool_calls for context continuity."""
    lines = ["<tool_calls>"]
    for tc in tool_calls:
        func = tc.get("function", {})
        name = func.get("name", "")
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str)
        except (json.JSONDecodeError, TypeError):
            args = {}
        
        lines.append(f'<invoke name="{name}">')
        for pname, pvalue in args.items():
            lines.append(f'<parameter name="{pname}">{pvalue}</parameter>')
        lines.append("</invoke>")
    lines.append("</tool_calls>")
    return "\n".join(lines)
