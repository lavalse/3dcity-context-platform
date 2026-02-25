from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.sql_generator import generate_sql
from app.database import run_query, QueryError

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    execute: bool = True  # if False, return SQL without running it


class QueryResponse(BaseModel):
    question: str
    sql: str
    explanation: str
    mode: str           # "llm" or "placeholder"
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    executed: bool = False
    error: str | None = None


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Step 1: generate SQL
    try:
        gen = await generate_sql(req.question)
    except Exception as e:
        return QueryResponse(
            question=req.question,
            sql="",
            explanation="",
            mode="error",
            error=f"SQL generation failed: {str(e)}",
        )

    response = QueryResponse(
        question=req.question,
        sql=gen["sql"],
        explanation=gen["explanation"],
        mode=gen["mode"],
    )

    # Step 2: execute (if requested)
    if req.execute:
        try:
            result = await run_query(gen["sql"])
            response.columns = result["columns"]
            response.rows = result["rows"]
            response.row_count = result["row_count"]
            response.executed = True
        except QueryError as e:
            response.error = str(e)
            response.executed = False

    return response
