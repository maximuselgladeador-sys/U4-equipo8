# Bitácora de escenarios E01–E15 (datos/escenarios.csv)

Ejecutados con `load_fixture()` y los CSV originales. No se modificó ninguna regla de negocio ni ningún dato.
Todas las pruebas están en `tests/test_domain.py`; resultado global: `python -m pytest -q` → 68 passed.

| Caso | Precondiciones (estado inicial) | Operación | Resultado real | Evento de dominio | Prueba |
|---|---|---|---|---|---|
| E01 | O001, C001 VIP activo, DRAFT, 4 uds, 2100.00, sin promo | evaluar descuento | 10 % (descuento 210.00, final 1890.00) | N/A (consulta) | `test_E01_O001_descuento_10` |
| E02 | O002, C002 no VIP, DRAFT, 2 uds, 1050.00 | evaluar descuento | 0 % | N/A | `test_E02_O002_no_vip_sin_descuento` |
| E03 | O003, C003 VIP **inactivo**, DRAFT, 4 uds, 2100.00 | `confirm()` | Rechazo: `InvalidOrderData` (HTTP 422); sigue DRAFT | Ninguno | `test_E03_O003_cliente_inactivo_rechaza_confirmar` |
| E04 | O005, C005 VIP, **promo activa**, 4 uds, 2100.00 | evaluar descuento | 0 % (la promo bloquea ambos) | N/A | `test_E04_O005_promocion_bloquea_descuento` |
| E05 | O006, C006 no VIP, 1 ud, 18000.00, sin promo | evaluar descuento | 5 % | N/A | `test_E05_O006_descuento_5` |
| E06 | O007, C007, DRAFT, sin artículos | `confirm()` | Rechazo: `InvalidOrderData` (422); sigue DRAFT | Ninguno | `test_E06_O007_pedido_sin_articulos_rechaza` |
| E07 | O008, C008, DRAFT, 20 uds, 2400.00 | `confirm()` | Éxito: CONFIRMED | `OrderConfirmed` | `test_E07_O008_20_unidades_se_confirma` |
| E08 | O009, C009, DRAFT, 19 uds | `add_item(SKU003 × 2)` | Rechazo: `OrderItemLimitExceeded`; sigue en 19 uds, 1 renglón | Ninguno | `test_E08_O009_agregar_2_supera_20` |
| E09 | O010, C010 no VIP, 2 uds, total exacto 500.00 | evaluar descuento | 0 % (500 no es > 500) | N/A | `test_E09_O010_umbral_estricto_500` |
| E10 | O011, C011 VIP, 3 uds, 1500.00, sin promo | evaluar descuento | 0 % (requiere ≥ 4 uds) | N/A | `test_E10_O011_vip_con_3_unidades` |
| E11 | O012, C012, DRAFT, 1 ud, 850.00 | `confirm()` y `ship("")` | Confirmación OK; envío rechazado: `InvalidOrderData` (422); queda CONFIRMED | Solo `OrderConfirmed` | `test_E11_O012_confirmar_y_enviar_sin_guia` |
| E12 | O013, C001, DRAFT, 1 ud, 600.00 | `confirm()` ×2 | 1.ª OK (CONFIRMED); 2.ª `InvalidOrderTransition` (409) | Solo un `OrderConfirmed` | `test_E12_O013_confirmar_dos_veces` |
| E13 | O014, C002, DRAFT, 1 ud, 600.00 | `confirm()`, `ship("GUIA-001")`, `cancel()` | Cancelación rechazada: `InvalidOrderTransition` (409); queda SHIPPED | `OrderConfirmed`, `OrderShipped` (sin `OrderCancelled`) | `test_E13_O014_cancelar_despues_de_enviar` |
| E14 | O015, C005, DRAFT, 1 ud, 450.00 | `confirm()`, `ship()`, `return_order()` | Éxito: RETURNED | `OrderConfirmed`, `OrderShipped`, `OrderReturned` | `test_E14_O015_devolucion_desde_shipped` |
| E15 | O016, C007, DRAFT, 1 ud, 2100.00 | `confirm()`, `ship()`, `deliver()` | Éxito: DELIVERED | `OrderConfirmed`, `OrderShipped`, `OrderDelivered` | `test_E15_O016_entrega_desde_shipped` |

Observaciones
- E09: O010 es cliente no VIP con 2 unidades, por lo que el descuento de 10 % se descarta por varias reglas; la prueba además verifica directamente que `MinimumAmountSpec(500)` no se cumple con total = 500.00 (umbral estricto).
- E03 y E04 no emiten evento porque la operación falla o es solo una consulta.
