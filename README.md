# TechStore U4 — Núcleo de negocio (DDD) con FastAPI y pytest

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install fastapi uvicorn pytest httpx
```
Incluye `datos/` y un `cargar_csv.py` de respaldo; si tu profesor te dio uno propio, reemplázalo (misma interfaz: `load_fixture()`).

## Ejecución
```bash
python cargar_csv.py                 # debe listar los 16 pedidos en DRAFT
python -m pytest -q                  # pruebas
uvicorn app.api:app --reload         # Swagger: http://127.0.0.1:8000/docs
```

## Reglas
- `Money`: `Decimal` (nunca float), no negativo, no suma monedas distintas.
- Máximo 20 unidades por pedido (suma de cantidades, no renglones).
- Descuento 10 %: VIP, total > 500, >= 4 unidades, sin promoción. Descuento 5 %: total > 5000, sin promoción. Si ambos aplican, 10 %.
- Estados: DRAFT → CONFIRMED → SHIPPED → DELIVERED | RETURNED; CONFIRMED → CANCELLED.
- Cada transición: validar → cambiar estado → registrar evento. Si falla, no hay evento.
- Sin control de inventario; repositorio en memoria (se pierde al cerrar).

## Endpoints
| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| GET | `/orders/{id}` | 200 | 404 |
| POST | `/orders/{id}/confirm` | 200 | 404, 409, 422 |
| POST | `/orders/{id}/ship` body `{"tracking_number": "..."}` | 200 | 404, 409, 422 |
| POST | `/orders/{id}/cancel` body `{"reason": "..."}` | 200 | 404, 409, 422 |

## Diagrama de estados
```
DRAFT --confirm--> CONFIRMED --ship--> SHIPPED --deliver--> DELIVERED
                       |                  |
                     cancel            return_order
                       v                  v
                   CANCELLED           RETURNED
```
