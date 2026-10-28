"""Núcleo de dominio de TechStore (Actividad 4).

Contiene Value Objects (Money), entidades (Customer, OrderItem), el Aggregate
Root (Order), la máquina de estados y los Domain Events.

Notas de diseño:
* Dinero SIEMPRE con Decimal; se rechaza float de forma explícita.
* El inventario pertenece al catálogo: aquí NO se descuenta existencia.
* El repositorio en memoria vive en la capa de API (diccionario).
* Secuencia estricta en cada transición: validar -> cambiar estado -> registrar evento.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum

MAX_UNITS_PER_ORDER = 20
CURRENCY = "MXN"


# --------------------------------------------------------------------------
# Excepciones de dominio
# --------------------------------------------------------------------------
class DomainException(Exception):
    """Base de todas las excepciones del dominio."""


class InvalidOrderData(DomainException):
    """Datos que violan una regla de negocio (-> HTTP 422)."""


class InvalidOrderTransition(DomainException):
    """Transición de estado no permitida (-> HTTP 409)."""


class OrderItemLimitExceeded(DomainException):
    """Se excede el máximo de 20 unidades por pedido."""


# --------------------------------------------------------------------------
# Value Object: Money
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = CURRENCY

    def __post_init__(self):
        amount = self.amount
        if isinstance(amount, (float, bool)):
            raise InvalidOrderData("Prohibido usar float/bool para dinero; use Decimal")
        if not isinstance(amount, Decimal):
            try:  # tolera int y str (p. ej. lecturas de CSV), nunca float
                amount = Decimal(str(amount))
            except (InvalidOperation, ValueError) as exc:
                raise InvalidOrderData("Monto inválido") from exc
            object.__setattr__(self, "amount", amount)
        if not amount.is_finite() or amount < 0:
            raise InvalidOrderData("Monto inválido")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise InvalidOrderData("Moneda inválida")

    def add(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            raise InvalidOrderData("Solo se puede sumar Money con Money")
        if self.currency != other.currency:
            raise InvalidOrderData("Monedas distintas")
        return Money(self.amount + other.amount, self.currency)


# --------------------------------------------------------------------------
# Entidades auxiliares
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Customer:
    id: str
    is_vip: bool = False
    active: bool = True


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not isinstance(self.sku, str) or not self.sku.strip():
            raise InvalidOrderData("Artículo inválido: SKU vacío")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity <= 0:
            raise InvalidOrderData("Artículo inválido: la cantidad debe ser un entero > 0")

    @property
    def subtotal(self) -> Money:
        """Se calcula siempre; nunca se captura a mano."""
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


# --------------------------------------------------------------------------
# Estados y eventos
# --------------------------------------------------------------------------
class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass(frozen=True)
class DomainEvent:
    name: str
    order_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detail: str = ""


# --------------------------------------------------------------------------
# Aggregate Root: Order
# --------------------------------------------------------------------------
@dataclass
class Order:
    customer: Customer
    id: str
    has_promotion: bool = False
    status: OrderStatus = OrderStatus.DRAFT
    items: list[OrderItem] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    tracking_number: str | None = None
    cancel_reason: str | None = None

    # ---- consultas ------------------------------------------------------
    @property
    def units(self) -> int:
        """Suma de unidades (no cuenta renglones)."""
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Money:
        amount = sum((x.subtotal.amount for x in self.items), Decimal("0"))
        return Money(amount)

    # ---- comandos -------------------------------------------------------
    def add_item(self, item: OrderItem) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT admite artículos")
        if item.unit_price.currency != CURRENCY:
            raise InvalidOrderData("Solo MXN")
        if self.units + item.quantity > MAX_UNITS_PER_ORDER:
            raise OrderItemLimitExceeded(f"Máximo {MAX_UNITS_PER_ORDER} unidades")
        self.items.append(item)

    def _emit(self, name: str, detail: str = "") -> None:
        self.events.append(DomainEvent(name, self.id, detail=detail))

    def _require_status(self, expected: OrderStatus, action: str) -> None:
        if self.status != expected:
            raise InvalidOrderTransition(
                f"No se puede {action} un pedido en estado {self.status.value}; se requiere {expected.value}"
            )

    def confirm(self) -> None:
        self._require_status(OrderStatus.DRAFT, "confirmar")
        if not self.items:
            raise InvalidOrderData("Requiere al menos un artículo")
        if not self.customer.active:
            raise InvalidOrderData("El cliente está inactivo")
        self.status = OrderStatus.CONFIRMED
        self._emit("OrderConfirmed")

    def ship(self, tracking_number: str) -> None:
        self._require_status(OrderStatus.CONFIRMED, "enviar")
        if not isinstance(tracking_number, str) or not tracking_number.strip():
            raise InvalidOrderData("El envío exige una guía de rastreo no vacía")
        self.status = OrderStatus.SHIPPED
        self.tracking_number = tracking_number.strip()
        self._emit("OrderShipped", self.tracking_number)

    def cancel(self, reason: str) -> None:
        self._require_status(OrderStatus.CONFIRMED, "cancelar")
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidOrderData("La cancelación exige un motivo no vacío")
        self.status = OrderStatus.CANCELLED
        self.cancel_reason = reason.strip()
        self._emit("OrderCancelled", self.cancel_reason)

    def deliver(self) -> None:
        self._require_status(OrderStatus.SHIPPED, "entregar")
        self.status = OrderStatus.DELIVERED
        self._emit("OrderDelivered")

    def return_order(self) -> None:
        self._require_status(OrderStatus.SHIPPED, "devolver")
        self.status = OrderStatus.RETURNED
        self._emit("OrderReturned")
