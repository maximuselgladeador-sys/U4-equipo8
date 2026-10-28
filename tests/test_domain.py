"""Pruebas del dominio TechStore (Actividad 4).

Los escenarios E01-E15 se construyen con objetos propios para que las pruebas
no dependan de editar los CSV. Al final hay pruebas contra los CSV reales
(load_fixture), que se omiten si cargar_csv.py / datos/ no están disponibles.
"""
from decimal import Decimal

import pytest

from app.domain import (
    Customer,
    InvalidOrderData,
    InvalidOrderTransition,
    Money,
    Order,
    OrderItem,
    OrderItemLimitExceeded,
    OrderStatus,
)
from app.specifications import (
    ActivePromotionSpec,
    MinimumAmountSpec,
    MinimumUnitsSpec,
    VIPCustomerSpec,
    discount_rate,
    five_percent_rule,
    ten_percent_rule,
)


# ---------------------------------------------------------------- helpers
def item(sku="SKU001", qty=1, price="100.00"):
    return OrderItem(sku, qty, Money(Decimal(price)))


def make_order(oid="T1", *, vip=False, active=True, promo=False, items=()):
    order = Order(customer=Customer("C1", is_vip=vip, active=active), id=oid, has_promotion=promo)
    for it in items:
        order.add_item(it)
    return order


def confirmed(oid="T1", **kw):
    order = make_order(oid, items=[item(qty=2)], **kw)
    order.confirm()
    return order


def shipped(oid="T1"):
    order = confirmed(oid)
    order.ship("GUIA-123")
    return order


def names(order):
    return [e.name for e in order.events]


# ---------------------------------------------------------------- Money
def test_money_negativo():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-1"))


def test_money_rechaza_float():
    with pytest.raises(InvalidOrderData):
        Money(600.0)


def test_money_rechaza_no_finito():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("NaN"))


def test_money_monedas_distintas():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("1"), "MXN").add(Money(Decimal("1"), "USD"))


def test_money_add_devuelve_objeto_nuevo_e_inmutable():
    a, b = Money(Decimal("1.50")), Money(Decimal("2.25"))
    c = a.add(b)
    assert c.amount == Decimal("3.75") and c is not a and a.amount == Decimal("1.50")
    with pytest.raises(Exception):
        a.amount = Decimal("9")  # frozen


# ---------------------------------------------------------------- OrderItem
@pytest.mark.parametrize("qty", [0, -1])
def test_item_cantidad_invalida(qty):
    with pytest.raises(InvalidOrderData):
        OrderItem("SKU001", qty, Money(Decimal("10")))


def test_item_subtotal_se_calcula():
    assert item(qty=3, price="600.00").subtotal.amount == Decimal("1800.00")


# ---------------------------------------------------------------- Specifications
def test_composicion_and_or_not():
    o = make_order(vip=True, items=[item(qty=4, price="200.00")])
    assert (VIPCustomerSpec() & MinimumUnitsSpec(4)).is_satisfied_by(o)
    assert (VIPCustomerSpec() | ActivePromotionSpec()).is_satisfied_by(o)
    assert (~ActivePromotionSpec()).is_satisfied_by(o)
    assert not (ActivePromotionSpec() & VIPCustomerSpec()).is_satisfied_by(o)


def test_minimum_amount_es_estricto():
    o = make_order(items=[item(qty=5, price="100.00")])  # total exacto 500
    assert not MinimumAmountSpec(Decimal("500")).is_satisfied_by(o)


# ---------------------------------------------------------------- E01-E05 descuentos
def test_unit_E01_descuento_10_vip():
    o = make_order(vip=True, items=[item("SKU001", 2, "600.00"), item("SKU002", 2, "450.00")])
    assert (o.units, o.total.amount) == (4, Decimal("2100.00"))
    assert ten_percent_rule.is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0.10")


def test_unit_E02_descuento_5_no_vip_total_mayor_5000():
    o = make_order(vip=False, items=[item(qty=3, price="2000.00")])  # 6000
    assert not ten_percent_rule.is_satisfied_by(o)
    assert five_percent_rule.is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0.05")


def test_unit_E03_ambas_reglas_aplica_primero_10():
    o = make_order(vip=True, items=[item(qty=4, price="2000.00")])  # 8000, VIP, 4 uds
    assert ten_percent_rule.is_satisfied_by(o) and five_percent_rule.is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0.10")


def test_unit_E04_promocion_activa_excluye_ambos_descuentos():
    o = make_order(vip=True, promo=True, items=[item(qty=4, price="2000.00")])
    assert not ten_percent_rule.is_satisfied_by(o)
    assert not five_percent_rule.is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0")


def test_unit_E05_total_exactamente_500_no_supera_umbral():
    o = make_order(vip=True, items=[item(qty=5, price="100.00")])
    assert o.total.amount == Decimal("500.00")
    assert discount_rate(o) == Decimal("0")


def test_vip_con_3_unidades_no_alcanza_10():
    o = make_order(vip=True, items=[item(qty=3, price="400.00")])
    assert discount_rate(o) == Decimal("0")


def test_total_exactamente_5000_no_obtiene_5():
    o = make_order(vip=False, items=[item(qty=5, price="1000.00")])
    assert discount_rate(o) == Decimal("0")


# ---------------------------------------------------------------- E06-E10 vacío / límite / cliente
def test_unit_E06_pedido_vacio_no_se_confirma():
    o = make_order()
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_unit_E07_20_unidades_en_muchos_renglones_es_valido():
    o = make_order(items=[item(f"SKU{i:03d}", 2) for i in range(10)])  # 10 renglones x 2
    assert o.units == 20 and len(o.items) == 10


def test_unit_E08_21_unidades_rechazadas():
    o = make_order(items=[item(qty=20)])
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(item("SKU002", 1))
    assert o.units == 20 and len(o.items) == 1


def test_limite_21_unidades_en_un_solo_renglon():
    o = make_order()
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(item(qty=21))
    assert o.items == []


def test_unit_E09_19_mas_2_rechazado_sin_modificar_items():
    o = make_order(items=[item("SKU001", 10), item("SKU002", 9)])
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(item("SKU003", 2))
    assert o.units == 19 and len(o.items) == 2


def test_unit_E10_cliente_inactivo_no_confirma():
    o = make_order(active=False, items=[item(qty=2)])
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_no_se_agregan_articulos_fuera_de_draft():
    o = confirmed()
    with pytest.raises(InvalidOrderTransition):
        o.add_item(item("SKU009", 1))


# ---------------------------------------------------------------- E11-E15 estados
def test_unit_E11_envio_sin_guia():
    o = confirmed()
    n = len(o.events)
    for bad in ("", "   "):
        with pytest.raises(InvalidOrderData):
            o.ship(bad)
    assert o.status == OrderStatus.CONFIRMED and len(o.events) == n


def test_unit_E12_confirmacion_doble():
    o = make_order("O013", items=[item(qty=2)])
    o.confirm()
    assert o.status == OrderStatus.CONFIRMED and names(o) == ["OrderConfirmed"]
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert names(o) == ["OrderConfirmed"]


def test_unit_E13_cancelar_desde_shipped_prohibido():
    o = shipped()
    n = len(o.events)
    with pytest.raises(InvalidOrderTransition):
        o.cancel("ya no lo quiero")
    assert o.status == OrderStatus.SHIPPED and len(o.events) == n


def test_unit_E14_devolucion_valida():
    o = shipped()
    o.return_order()
    assert o.status == OrderStatus.RETURNED
    assert names(o) == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


def test_unit_E15_entrega_valida():
    o = shipped()
    o.deliver()
    assert o.status == OrderStatus.DELIVERED
    assert names(o) == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]


# ---------------------------------------------------------------- más reglas de estado
def test_cancelar_desde_confirmed_con_motivo():
    o = confirmed()
    o.cancel("cambio de opinión")
    assert o.status == OrderStatus.CANCELLED and names(o)[-1] == "OrderCancelled"


def test_cancelar_sin_motivo_falla_sin_evento():
    o = confirmed()
    with pytest.raises(InvalidOrderData):
        o.cancel("  ")
    assert o.status == OrderStatus.CONFIRMED and names(o) == ["OrderConfirmed"]


def test_transiciones_invalidas_desde_draft():
    o = make_order(items=[item()])
    for call in (lambda: o.ship("G1"), lambda: o.cancel("x"), o.deliver, o.return_order):
        with pytest.raises(InvalidOrderTransition):
            call()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_estados_terminales_no_avanzan():
    for final in ("deliver", "return_order"):
        o = shipped()
        getattr(o, final)()
        n = len(o.events)
        for call in (o.confirm, lambda: o.ship("G"), lambda: o.cancel("x"), o.deliver, o.return_order):
            with pytest.raises(InvalidOrderTransition):
                call()
        assert len(o.events) == n


# ---------------------------------------------------------------- contra los CSV reales
@pytest.fixture
def csv_orders():
    cargar = pytest.importorskip("cargar_csv")
    try:
        return cargar.load_fixture()
    except FileNotFoundError:
        pytest.skip("No se encontró la carpeta datos/")


def test_csv_16_pedidos_todos_draft(csv_orders):
    assert len(csv_orders) == 16
    assert all(o.status == OrderStatus.DRAFT for o in csv_orders.values())


def test_csv_o001(csv_orders):
    o = csv_orders["O001"]
    assert o.units == 4 and o.total.amount == Decimal("2100.00")
    assert discount_rate(o) == Decimal("0.10")


def test_csv_o005_promocion_sin_descuento(csv_orders):
    o = csv_orders["O005"]
    assert o.has_promotion and discount_rate(o) == Decimal("0")


def test_csv_o006_descuento_5(csv_orders):
    assert discount_rate(csv_orders["O006"]) == Decimal("0.05")


def test_csv_o010_total_500_sin_descuento(csv_orders):
    o = csv_orders["O010"]
    assert o.total.amount == Decimal("500.00") and discount_rate(o) == Decimal("0")


def test_csv_o013_confirmacion_doble(csv_orders):
    o = csv_orders["O013"]
    o.confirm()
    assert names(o) == ["OrderConfirmed"]
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert names(o) == ["OrderConfirmed"]


# ======================================================================
# Escenarios E01-E15 de datos/escenarios.csv, ejecutados con los CSV reales
# ======================================================================
def _ship(o):
    o.confirm()
    o.ship("GUIA-001")


def test_E01_O001_descuento_10(csv_orders):
    o = csv_orders["O001"]
    assert o.customer.is_vip and o.units == 4 and o.total.amount == Decimal("2100.00")
    assert discount_rate(o) == Decimal("0.10")


def test_E02_O002_no_vip_sin_descuento(csv_orders):
    o = csv_orders["O002"]
    assert not o.customer.is_vip and o.total.amount == Decimal("1050.00")
    assert discount_rate(o) == Decimal("0")


def test_E03_O003_cliente_inactivo_rechaza_confirmar(csv_orders):
    o = csv_orders["O003"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_E04_O005_promocion_bloquea_descuento(csv_orders):
    o = csv_orders["O005"]
    assert o.has_promotion and o.customer.is_vip and o.units >= 4
    assert discount_rate(o) == Decimal("0")


def test_E05_O006_descuento_5(csv_orders):
    o = csv_orders["O006"]
    assert o.total.amount == Decimal("18000.00")
    assert not ten_percent_rule.is_satisfied_by(o) and five_percent_rule.is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0.05")


def test_E06_O007_pedido_sin_articulos_rechaza(csv_orders):
    o = csv_orders["O007"]
    assert o.units == 0
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_E07_O008_20_unidades_se_confirma(csv_orders):
    o = csv_orders["O008"]
    assert o.units == 20
    o.confirm()
    assert o.status == OrderStatus.CONFIRMED and names(o) == ["OrderConfirmed"]


def test_E08_O009_agregar_2_supera_20(csv_orders):
    o = csv_orders["O009"]
    assert o.units == 19
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
    assert o.units == 19 and len(o.items) == 1 and o.events == []


def test_E09_O010_umbral_estricto_500(csv_orders):
    o = csv_orders["O010"]
    assert o.total.amount == Decimal("500.00")
    assert not MinimumAmountSpec(Decimal("500")).is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0")


def test_E10_O011_vip_con_3_unidades(csv_orders):
    o = csv_orders["O011"]
    assert o.customer.is_vip and o.units == 3 and o.total.amount > Decimal("500")
    assert not MinimumUnitsSpec(4).is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0")


def test_E11_O012_confirmar_y_enviar_sin_guia(csv_orders):
    o = csv_orders["O012"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.ship("")
    assert o.status == OrderStatus.CONFIRMED and names(o) == ["OrderConfirmed"]


def test_E12_O013_confirmar_dos_veces(csv_orders):
    o = csv_orders["O013"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert o.status == OrderStatus.CONFIRMED and names(o) == ["OrderConfirmed"]


def test_E13_O014_cancelar_despues_de_enviar(csv_orders):
    o = csv_orders["O014"]
    _ship(o)
    with pytest.raises(InvalidOrderTransition):
        o.cancel("ya no lo quiero")
    assert o.status == OrderStatus.SHIPPED and names(o) == ["OrderConfirmed", "OrderShipped"]


def test_E14_O015_devolucion_desde_shipped(csv_orders):
    o = csv_orders["O015"]
    _ship(o)
    o.return_order()
    assert o.status == OrderStatus.RETURNED
    assert names(o) == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


def test_E15_O016_entrega_desde_shipped(csv_orders):
    o = csv_orders["O016"]
    _ship(o)
    o.deliver()
    assert o.status == OrderStatus.DELIVERED
    assert names(o) == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]
