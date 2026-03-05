"""
Conversational chat endpoint with streaming SSE.

Flow: Sonnet agentic tool-use loop — Sonnet drives the entire conversation,
calling execute_sql one or more times per turn (auto-retry on empty results or
errors), then streams a natural-language interpretation.
"""

import decimal
import datetime
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.database import run_query, QueryError

class _JsonEncoder(json.JSONEncoder):
    """Handle types asyncpg returns that stdlib json can't serialize."""
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.hex()
        return super().default(obj)


router = APIRouter()

EXECUTE_SQL_TOOL = {
    "name": "execute_sql",
    "description": "Execute a SELECT SQL query against the 3DCityDB PostgreSQL database and return results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "The PostgreSQL SELECT query to execute",
            },
            "explanation": {
                "type": "string",
                "description": "Brief one-line explanation of what this query does (in Japanese)",
            },
        },
        "required": ["sql"],
    },
}

_CHAT_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "chat_system_prompt.md"


def _load_chat_system_prompt() -> str:
    return _CHAT_PROMPT_PATH.read_text(encoding="utf-8")


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str | list


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, cls=_JsonEncoder)}\n\n"


MAX_TOOL_ROUNDS = 4


async def _chat_stream(messages: list[ChatMessage]):
    settings = get_settings()

    if not settings.use_llm:
        yield _sse({
            "type": "error",
            "message": "チャット機能にはClaude APIキーが必要です。管理者にお問い合わせいただくか、クエリタブをお使いください。",
            "retrying": False,
        })
        yield _sse({"type": "done"})
        return

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        system = _load_chat_system_prompt()
        messages_so_far = [m.model_dump() for m in messages]

        force_last_round = False
        for round_num in range(MAX_TOOL_ROUNDS + 1):
            is_last_round = (round_num == MAX_TOOL_ROUNDS) or force_last_round
            thinking_msg = "SQLを生成中…" if round_num == 0 else "追加クエリを実行中…"
            yield _sse({"type": "thinking", "message": thinking_msg, "round": round_num})

            # On the final round, if the last user message contains only tool_result
            # blocks (e.g. raw WKB geometry), the model may emit zero text tokens
            # because it wants to call a tool but tools=[]. Inject a directing text
            # block so it summarises in Japanese instead.
            api_messages = messages_so_far
            if is_last_round and messages_so_far:
                last = messages_so_far[-1]
                if (last["role"] == "user"
                        and isinstance(last["content"], list)
                        and any(b.get("type") == "tool_result" for b in last["content"])
                        and not any(b.get("type") == "text" for b in last["content"])):
                    api_messages = messages_so_far[:-1] + [{
                        **last,
                        "content": last["content"] + [{
                            "type": "text",
                            "text": "以上の結果を日本語でまとめてください。追加クエリは不要です。",
                        }],
                    }]

            buffered_text = []
            async with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096 if is_last_round else 1024,
                system=system,
                tools=[] if is_last_round else [EXECUTE_SQL_TOOL],
                messages=api_messages,
            ) as stream:
                if is_last_round:
                    # Final interpretation round: stream in real-time (no tools possible)
                    async for text in stream.text_stream:
                        yield _sse({"type": "token", "content": text, "round": round_num})
                else:
                    # Tool-use round: buffer text to suppress planning preamble
                    async for text in stream.text_stream:
                        buffered_text.append(text)
                final_msg = await stream.get_final_message()

            messages_so_far.append({
                "role": "assistant",
                "content": [block.model_dump() for block in final_msg.content],
            })

            if final_msg.stop_reason == "end_turn" or is_last_round:
                # Flush buffered text if model responded without calling a tool
                for text in buffered_text:
                    yield _sse({"type": "token", "content": text, "round": round_num})
                yield _sse({"type": "done"})
                return

            # Process tool calls
            tool_results = []
            got_nonempty_result = False
            for block in final_msg.content:
                if block.type == "tool_use" and block.name == "execute_sql":
                    sql = block.input["sql"]
                    explanation = block.input.get("explanation", "")
                    yield _sse({"type": "sql", "sql": sql, "explanation": explanation, "round": round_num})
                    yield _sse({"type": "executing", "message": "クエリを実行中…", "round": round_num})
                    try:
                        result = await run_query(sql)
                        tool_result_content = json.dumps(
                            {"columns": result["columns"],
                             "rows": result["rows"][:50],
                             "row_count": result["row_count"]},
                            ensure_ascii=False, cls=_JsonEncoder,
                        )
                        yield _sse({"type": "results",
                                    "columns": result["columns"],
                                    "rows": result["rows"],
                                    "row_count": result["row_count"],
                                    "round": round_num})
                        if result["row_count"] > 0:
                            got_nonempty_result = True
                    except QueryError as e:
                        tool_result_content = f"SQL execution failed: {str(e)}"
                        yield _sse({"type": "error", "message": str(e), "retrying": True, "round": round_num})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result_content,
                    })

            if not tool_results:
                force_last_round = True
                continue

            if got_nonempty_result:
                force_last_round = True
            messages_so_far.append({"role": "user", "content": tool_results})

    except Exception as exc:
        yield _sse({"type": "error", "message": f"サーバーエラー: {exc}", "retrying": False})
        yield _sse({"type": "done"})


@router.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        _chat_stream(req.messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
