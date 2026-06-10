import json
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.funpay_client import (
    FunPayNotConfiguredError,
    FunPayPurchaseFlowError,
    FunPayUnsupportedOperationError,
    exceptions,
    funpay_client,
)
from app.parser import FunPayUpstreamTimeoutError, LotSearchFilters, fetch_funpay_warranty, search_lots

app = FastAPI(title="FunPayBot API", version="0.1.0")


class LotSearchRequest(BaseModel):
    query: str = ""
    search_scope: Literal["category", "site"] = "category"
    max_price: Decimal | None = None
    min_reviews: int = Field(default=0, ge=0)
    forbidden_words: list[str] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    chat_id: str
    body: str = Field(min_length=1)


class CreateOrderRequest(BaseModel):
    lot_url: str
    payment_method_id: str = Field(min_length=1)


class PaymentMethodsRequest(BaseModel):
    lot_url: str


def map_funpay_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FunPayNotConfiguredError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, FunPayUnsupportedOperationError):
        return HTTPException(status_code=501, detail=str(exc))
    if isinstance(exc, FunPayPurchaseFlowError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, exceptions.UnauthorizedError):
        return HTTPException(status_code=401, detail="FunPay session is unauthorized")
    if isinstance(exc, exceptions.RequestFailedError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "funpay_configured": funpay_client.configured}


@app.get("/session")
async def session_get() -> dict:
    return await funpay_client.session_status()


@app.post("/session/refresh")
async def session_refresh() -> dict:
    try:
        return await funpay_client.refresh_session()
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.post("/lots/search")
async def lots_search(request: LotSearchRequest) -> dict:
    filters = LotSearchFilters(
        query=request.query,
        max_price=request.max_price,
        min_reviews=request.min_reviews,
        forbidden_words=tuple(request.forbidden_words),
    )
    try:
        lots = await search_lots(filters, scope=request.search_scope)
    except FunPayUpstreamTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
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
        try:
            lots = await search_lots(filters)
        except FunPayUpstreamTimeoutError as exc:
            payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"
            return
        payload = json.dumps({"count": len(lots), "results": lots}, ensure_ascii=False)
        yield f"event: complete\ndata: {payload}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/lots/warranty")
async def lot_warranty(url: str, title: str | None = None) -> dict:
    try:
        warranty = await fetch_funpay_warranty(url, title=title)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"url": url, "warranty": warranty}


@app.post("/chats/send")
async def chats_send(request: SendMessageRequest) -> dict:
    try:
        return await funpay_client.send_message(request.chat_id, request.body)
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.get("/chats/messages")
async def chats_messages(chat_id: str | None = None) -> dict:
    try:
        return {"messages": await funpay_client.fetch_messages(chat_id)}
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.get("/chats")
async def chats_list(update: bool = True) -> dict:
    try:
        return {"chats": await funpay_client.list_chats(update=update)}
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.get("/chats/{chat_id}")
async def chats_get(chat_id: int) -> dict:
    try:
        return {"chat": await funpay_client.get_chat(chat_id)}
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.get("/chats/{chat_id}/history")
async def chats_history(
    chat_id: str,
    last_message_id: int | None = None,
    interlocutor_username: str | None = None,
    from_id: int = 0,
) -> dict:
    try:
        return {
            "messages": await funpay_client.get_chat_history(
                chat_id,
                last_message_id=last_message_id,
                interlocutor_username=interlocutor_username,
                from_id=from_id,
            )
        }
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.get("/orders/{order_id}")
async def orders_get(order_id: str) -> dict:
    try:
        return {"order": await funpay_client.get_order(order_id)}
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.post("/orders/{order_id}/refund")
async def orders_refund(order_id: str) -> dict:
    try:
        return await funpay_client.refund_order(order_id)
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.post("/orders")
async def orders_create(request: CreateOrderRequest) -> dict:
    try:
        return await funpay_client.create_order(request.lot_url, request.payment_method_id)
    except Exception as exc:
        raise map_funpay_error(exc) from exc


@app.post("/orders/payment-methods")
async def order_payment_methods(request: PaymentMethodsRequest) -> dict:
    try:
        return await funpay_client.list_payment_methods(request.lot_url)
    except Exception as exc:
        raise map_funpay_error(exc) from exc
