"""Patrón Specification y reglas de descuento de TechStore.

Una Specification solo responde True/False; nunca modifica el pedido.
Operadores: & (AND), | (OR), ~ (NOT).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain import Money


class Specification:
    def is_satisfied_by(self, order) -> bool:
        raise NotImplementedError

    def __and__(self, other: "Specification") -> "Specification":
        return AndSpec(self, other)

    def __or__(self, other: "Specification") -> "Specification":
        return OrSpec(self, other)

    def __invert__(self) -> "Specification":
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left, self.right = left, right

    def is_satisfied_by(self, order) -> bool:
        return self.left.is_satisfied_by(order) and self.right.is_satisfied_by(order)


class OrSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left, self.right = left, right

    def is_satisfied_by(self, order) -> bool:
        return self.left.is_satisfied_by(order) or self.right.is_satisfied_by(order)


class NotSpec(Specification):
    def __init__(self, inner: Specification):
        self.inner = inner

    def is_satisfied_by(self, order) -> bool:
        return not self.inner.is_satisfied_by(order)


# ---- reglas atómicas -------------------------------------------------------
class MinimumAmountSpec(Specification):
    """Total ESTRICTAMENTE mayor al umbral (>, no >=)."""

    def __init__(self, threshold: Decimal):
        if isinstance(threshold, float):
            raise TypeError("Use Decimal, no float")
        self.threshold = Decimal(threshold)

    def is_satisfied_by(self, order) -> bool:
        return order.total.amount > self.threshold


class VIPCustomerSpec(Specification):
    def is_satisfied_by(self, order) -> bool:
        return bool(order.customer.is_vip)


class MinimumUnitsSpec(Specification):
    """Al menos N unidades (>=)."""

    def __init__(self, minimum: int):
        self.minimum = minimum

    def is_satisfied_by(self, order) -> bool:
        return order.units >= self.minimum


class ActivePromotionSpec(Specification):
    def is_satisfied_by(self, order) -> bool:
        return bool(order.has_promotion)


# ---- reglas de descuento ---------------------------------------------------
TEN_PERCENT = Decimal("0.10")
FIVE_PERCENT = Decimal("0.05")
NO_DISCOUNT = Decimal("0")

# 10 %: VIP, total > 500, >= 4 unidades y SIN promoción activa
ten_percent_rule = (
    MinimumAmountSpec(Decimal("500"))
    & VIPCustomerSpec()
    & MinimumUnitsSpec(4)
    & ~ActivePromotionSpec()
)

# 5 %: total > 5000 y SIN promoción activa
five_percent_rule = MinimumAmountSpec(Decimal("5000")) & ~ActivePromotionSpec()

# Combinación de ambas reglas (OR): ¿el pedido tiene derecho a algún descuento?
any_discount_rule = ten_percent_rule | five_percent_rule


def discount_rate(order) -> Decimal:
    """Tasa de descuento. Prioridad: si se cumplen ambas, se aplica primero el 10 %."""
    if ten_percent_rule.is_satisfied_by(order):
        return TEN_PERCENT
    if five_percent_rule.is_satisfied_by(order):
        return FIVE_PERCENT
    return NO_DISCOUNT


def discount_amount(order) -> Money:
    amount = (order.total.amount * discount_rate(order)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return Money(amount)


def final_total(order) -> Money:
    return Money(order.total.amount - discount_amount(order).amount)
