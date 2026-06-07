import json
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.funpay_client import funpay_client
from app.parser import LotSearchFilters, fetch_funpay_warranty, search_lots

app = FastAPI(title="FunPayBot API", version="0.1.0")


class LotSearchRequest(BaseModel):
    query: str = ""
    max_price: Decimal | None = None
    min_reviews: int = Field(default=0, ge=0)
    forbidden_words: list[str] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    chat_id: str
    body: str = Field(min_length=1)


class CreateOrderRequest(BaseModel):
    lot_url: str


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "funpay_configured": funpay_client.configured}


@app.post("/lots/search")
async def lots_search(request: LotSearchRequest) -> dict:
    filters = LotSearchFilters(
        query=request.query,
        max_price=request.max_price,
        min_reviews=request.min_reviews,
        forbidden_words=tuple(request.forbidden_words),
    )
    lots = await search_lots(filters)
    return {"results": lots, "count": len(lots)}


@app.get("/lots/search/stream")
async def lots_search_stream(
    query: str = "",
    max_price: Decimal | None = None,
    min_reviews: int = Query(default=0, ge=0),
    forbidden_words: str = "",
) -> StreamingResponse:
    async def events():
        yield "event: progress\ndata: {\"stage\":\"fetching\"}\n\n"
        filters = LotSearchFilters(
            query=query,
            max_price=max_price,
            min_reviews=min_reviews,
            forbidden_words=tuple(word.strip() for word in forbidden_words.split(",") if word.strip()),
        )
        lots = await search_lots(filters)
        payload = json.dumps({"count": len(lots), "results": lots}, ensure_ascii=False)
        yield f"event: complete\ndata: {payload}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/lots/warranty")
async def lot_warranty(url: str) -> dict:
    try:
        warranty = await fetch_funpay_warranty(url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"url": url, "warranty": warranty}


@app.post("/chats/send")
async def chats_send(request: SendMessageRequest) -> dict:
    return await funpay_client.send_message(request.chat_id, request.body)


@app.get("/chats/messages")
async def chats_messages() -> dict:
    return {"messages": await funpay_client.fetch_messages()}


@app.post("/orders")
async def orders_create(request: CreateOrderRequest) -> dict:
    return await funpay_client.create_order(request.lot_url)
