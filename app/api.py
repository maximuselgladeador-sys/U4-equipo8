"""API REST de TechStore (FastAPI). Los controladores NO duplican reglas de negocio."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.domain import InvalidOrderData, InvalidOrderTransition, OrderItemLimitExceeded
from app.specifications import discount_amount, discount_rate, final_total
from cargar_csv import load_fixture

app = FastAPI(title="TechStore U4")

# Repositorio en memoria: se pierde al cerrar el programa.
orders = load_fixture()


class ShipRequest(BaseModel):
    tracking_number: str = ""


class CancelRequest(BaseModel):
    reason: str = ""


def _get_order(order_id: str):
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="No existe")
    return order


def _run(action, *args):
    """Ejecuta un método del dominio y traduce sus excepciones a HTTP."""
    try:
        action(*args)
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (InvalidOrderData, OrderItemLimitExceeded) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _summary(order) -> dict:
    return {"id": order.id, "status": order.status.value}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = _get_order(order_id)
    return {
        "id": order.id,
        "status": order.status.value,
        "customer_id": order.customer.id,
        "has_promotion": order.has_promotion,
        "units": order.units,
        "total": str(order.total.amount),
        "currency": order.total.currency,
        "discount_rate": str(discount_rate(order)),
        "discount_amount": str(discount_amount(order).amount),
        "final_total": str(final_total(order).amount),
        "tracking_number": order.tracking_number,
        "cancel_reason": order.cancel_reason,
        "events": [e.name for e in order.events],
    }


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str):
    order = _get_order(order_id)
    _run(order.confirm)
    return _summary(order)


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, body: ShipRequest):
    order = _get_order(order_id)
    _run(order.ship, body.tracking_number)
    return {**_summary(order), "tracking_number": order.tracking_number}


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, body: CancelRequest):
    order = _get_order(order_id)
    _run(order.cancel, body.reason)
    return {**_summary(order), "cancel_reason": order.cancel_reason}
