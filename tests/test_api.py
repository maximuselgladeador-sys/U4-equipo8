"""Pruebas de la API REST (FastAPI + TestClient).

Cada prueba reemplaza el repositorio en memoria por pedidos propios, así los
casos son independientes y no dependen de reiniciar el servidor.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import api
from app.domain import Customer, Money, Order, OrderItem


def build(oid, *, qty=2, price="100.00", vip=False, active=True, promo=False):
    order = Order(customer=Customer("C1", is_vip=vip, active=active), id=oid, has_promotion=promo)
    if qty:
        order.add_item(OrderItem("SKU001", qty, Money(Decimal(price))))
    return order


@pytest.fixture
def client(monkeypatch):
    repo = {
        "A1": build("A1"),
        "VACIO": build("VACIO", qty=0),
        "INACTIVO": build("INACTIVO", active=False),
        "VIP": build("VIP", qty=4, price="600.00", vip=True),
    }
    monkeypatch.setattr(api, "orders", repo)
    return TestClient(api.app)


# ------------------------------------------------------------------ 404
def test_get_inexistente_404(client):
    assert client.get("/orders/NOPE").status_code == 404


@pytest.mark.parametrize(
    "path,body",
    [("confirm", None), ("ship", {"tracking_number": "G1"}), ("cancel", {"reason": "x"})],
)
def test_post_inexistente_404(client, path, body):
    assert client.post(f"/orders/NOPE/{path}", json=body).status_code == 404


# ------------------------------------------------------------------ flujo exitoso
def test_get_pedido_existente(client):
    r = client.get("/orders/VIP")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "DRAFT" and data["units"] == 4
    assert data["total"] == "2400.00" and data["discount_rate"] == "0.10"


def test_confirmar_y_enviar_200(client):
    assert client.post("/orders/A1/confirm").json() == {"id": "A1", "status": "CONFIRMED"}
    r = client.post("/orders/A1/ship", json={"tracking_number": "GUIA-1"})
    assert r.status_code == 200 and r.json()["status"] == "SHIPPED"
    assert client.get("/orders/A1").json()["events"] == ["OrderConfirmed", "OrderShipped"]


def test_cancelar_200(client):
    client.post("/orders/A1/confirm")
    r = client.post("/orders/A1/cancel", json={"reason": "cliente se arrepintió"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


# ------------------------------------------------------------------ 409
def test_confirmacion_doble_409_sin_evento_extra(client):
    assert client.post("/orders/A1/confirm").status_code == 200
    assert client.post("/orders/A1/confirm").status_code == 409
    assert client.get("/orders/A1").json()["events"] == ["OrderConfirmed"]


def test_enviar_desde_draft_409(client):
    assert client.post("/orders/A1/ship", json={"tracking_number": "G1"}).status_code == 409


def test_cancelar_desde_shipped_409(client):
    client.post("/orders/A1/confirm")
    client.post("/orders/A1/ship", json={"tracking_number": "G1"})
    assert client.post("/orders/A1/cancel", json={"reason": "tarde"}).status_code == 409
    assert client.get("/orders/A1").json()["status"] == "SHIPPED"


# ------------------------------------------------------------------ 422
def test_confirmar_pedido_vacio_422(client):
    assert client.post("/orders/VACIO/confirm").status_code == 422


def test_confirmar_cliente_inactivo_422(client):
    assert client.post("/orders/INACTIVO/confirm").status_code == 422


def test_enviar_sin_guia_422(client):
    client.post("/orders/A1/confirm")
    assert client.post("/orders/A1/ship", json={"tracking_number": ""}).status_code == 422
    assert client.post("/orders/A1/ship", json={}).status_code == 422
    assert client.get("/orders/A1").json()["status"] == "CONFIRMED"


def test_cancelar_sin_motivo_422(client):
    client.post("/orders/A1/confirm")
    assert client.post("/orders/A1/cancel", json={"reason": " "}).status_code == 422
