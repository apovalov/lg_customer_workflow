# agent_src/tools.py
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

# ChromaDB retrieval tool
from clients.vector_db import vector_db_client
from config import settings

# DB: psycopg (v3)
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as e:
    raise ImportError(
        "psycopg is required for SQL tools. Add to pyproject: psycopg[binary]>=3.2"
    ) from e


# ---- DB helpers --------------------------------------------------------------

def _get_db_url() -> str:
    # Prefer config.Settings computed_database_url
    try:
        from config import settings  # type: ignore
        return settings.computed_database_url
    except Exception:
        pass
    env_url = os.getenv("DATABASE_URL")
    if not env_url:
        raise RuntimeError(
            "DATABASE_URL is not set and config.settings.computed_database_url is missing."
        )
    return env_url


def _connect():
    return psycopg.connect(_get_db_url(), row_factory=dict_row)


def _fetch_one(sql: str, params: Tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"Database error in _fetch_one: {e}")
        return None


def _fetch_all(sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        print(f"Database error in _fetch_all: {e}")
        return []


# ---- RAG retrieval tool (updated for CS knowledge base) ---------------------

@tool
def retrieve_support_docs(query: str) -> dict:
    """
    Retrieve relevant customer support documentation chunks from the knowledge base for a given query.
    Returns a dict with a 'chunks' key containing a list of relevant text chunks.
    """
    results = vector_db_client.similarity_search(query, k=settings.top_k)
    all_chunks = []
    # Since the chunks in the vector store are relatively short (about 400 characters),
    # which is good for retrieval precision but may not provide enough context for a complete answer,
    # we retrieve not only the most similar chunk but also its immediate neighbors.
    # This ensures that the returned context is sufficiently rich and
    # the answer is less likely to be truncated or missing important details.
    for doc in results:
        # Retrieve the current, previous, and next chunk for the file in a single query
        filename = doc.metadata.get("filename")
        chunk_index = doc.metadata.get("chunk_index")
        if filename is not None and chunk_index is not None:
            neighbor_docs = vector_db_client.db.get(
                where={
                    "$and": [
                        {"filename": filename},
                        {
                            "chunk_index": {
                                "$in": [chunk_index - 1, chunk_index, chunk_index + 1]
                            }
                        },
                    ]
                }
            )
            all_chunks.extend(neighbor_docs.get("documents", []))
    return {"chunks": all_chunks}


# ---- TRACKING_STATUS tools ---------------------------------------------------

@tool
def tool_track_order_basic(order_id: int) -> Dict[str, Any]:
    """
    Get basic tracking snapshot by order_id.
    Returns: found(bool), order_id, status, tracking_no, carrier, eta_date (ISO), last_shipment_event (if any).
    """
    order_sql = """
        SELECT o.order_id, o.status, o.tracking_no, o.carrier, o.eta_date
        FROM orders o
        WHERE o.order_id = %s
        LIMIT 1;
    """
    order = _fetch_one(order_sql, (order_id,))
    if not order:
        return {"found": False, "order_id": order_id}

    last_evt_sql = """
        SELECT status, location, event_time, details
        FROM shipment_events
        WHERE tracking_no = %s
        ORDER BY event_time DESC
        LIMIT 1;
    """
    last_evt = _fetch_one(last_evt_sql, (order.get("tracking_no"),))
    if last_evt and last_evt.get("event_time"):
        # ensure iso
        try:
            last_evt["event_time"] = (
                last_evt["event_time"].astimezone(timezone.utc).isoformat()
                if hasattr(last_evt["event_time"], "astimezone")
                else str(last_evt["event_time"])
            )
        except Exception:
            last_evt["event_time"] = str(last_evt["event_time"])

    # normalize eta
    if order.get("eta_date"):
        try:
            order["eta_date"] = (
                order["eta_date"].astimezone(timezone.utc).isoformat()
                if hasattr(order["eta_date"], "astimezone")
                else str(order["eta_date"])
            )
        except Exception:
            order["eta_date"] = str(order["eta_date"])

    return {"found": True, **order, "last_shipment_event": last_evt}


@tool
def tool_track_by_tracking_no(tracking_no: str) -> Dict[str, Any]:
    """
    Get current order + last shipment event by tracking_no.
    Returns: found, order_id, status, carrier, eta_date, last_event{status,location,event_time,details}
    """
    order_sql = """
        SELECT order_id, status, carrier, eta_date
        FROM orders
        WHERE tracking_no = %s
        LIMIT 1;
    """
    order = _fetch_one(order_sql, (tracking_no,))
    if not order:
        return {"found": False, "tracking_no": tracking_no}

    last_evt_sql = """
        SELECT status, location, event_time, details
        FROM shipment_events
        WHERE tracking_no = %s
        ORDER BY event_time DESC
        LIMIT 1;
    """
    last_evt = _fetch_one(last_evt_sql, (tracking_no,))
    if last_evt and last_evt.get("event_time"):
        try:
            last_evt["event_time"] = (
                last_evt["event_time"].astimezone(timezone.utc).isoformat()
                if hasattr(last_evt["event_time"], "astimezone")
                else str(last_evt["event_time"])
            )
        except Exception:
            last_evt["event_time"] = str(last_evt["event_time"])

    if order.get("eta_date"):
        try:
            order["eta_date"] = (
                order["eta_date"].astimezone(timezone.utc).isoformat()
                if hasattr(order["eta_date"], "astimezone")
                else str(order["eta_date"])
            )
        except Exception:
            order["eta_date"] = str(order["eta_date"])

    return {"found": True, "tracking_no": tracking_no, **order, "last_event": last_evt}


@tool
def tool_track_latest_status(order_id: int) -> Dict[str, Any]:
    """
    Get the very latest shipment status for an order_id (joins through tracking_no).
    Useful to surface 'Shipment on Hold' cases.
    Returns: found, order_id, tracking_no, latest{status,location,event_time,details}
    """
    t_sql = "SELECT tracking_no FROM orders WHERE order_id = %s LIMIT 1;"
    t = _fetch_one(t_sql, (order_id,))
    if not t or not t.get("tracking_no"):
        return {"found": False, "order_id": order_id}

    ev_sql = """
        SELECT status, location, event_time, details
        FROM shipment_events
        WHERE tracking_no = %s
        ORDER BY event_time DESC
        LIMIT 1;
    """
    last_evt = _fetch_one(ev_sql, (t["tracking_no"],))
    if last_evt and last_evt.get("event_time"):
        try:
            last_evt["event_time"] = (
                last_evt["event_time"].astimezone(timezone.utc).isoformat()
                if hasattr(last_evt["event_time"], "astimezone")
                else str(last_evt["event_time"])
            )
        except Exception:
            last_evt["event_time"] = str(last_evt["event_time"])

    return {
        "found": True if last_evt else False,
        "order_id": order_id,
        "tracking_no": t["tracking_no"],
        "latest": last_evt,
    }


# ---- DELIVERY_OPTIONS tools --------------------------------------------------

@tool
def tool_delivery_options_by_region(region: str) -> Dict[str, Any]:
    """
    List available shipping methods for region (fallback to 'World').
    Returns: methods: [{name, carrier, cost, est_days_min, est_days_max}]
    """
    sql = """
        SELECT name, carrier, cost, est_days_min, est_days_max
        FROM shipping_methods
        WHERE region IN (%s, 'World')
        ORDER BY cost ASC, est_days_min ASC;
    """
    rows = _fetch_all(sql, (region,))
    return {"region": region, "methods": rows}


@tool
def tool_cheapest_delivery(region: str, max_days: Optional[int] = None) -> Dict[str, Any]:
    """
    Get the cheapest delivery option for a region, optionally under an SLA threshold (max_days).
    Returns: found, option{ name, carrier, cost, est_days_min, est_days_max }
    """
    base = """
        SELECT name, carrier, cost, est_days_min, est_days_max
        FROM shipping_methods
        WHERE region IN (%s, 'World')
    """
    params: List[Any] = [region]
    if max_days is not None:
        base += " AND est_days_max <= %s"
        params.append(max_days)
    base += " ORDER BY cost ASC, est_days_min ASC LIMIT 1;"

    row = _fetch_one(base, tuple(params))
    return {"found": bool(row), "region": region, "option": row}


@tool
def tool_estimate_delivery_cost(region: str, method_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Estimate delivery cost and ETA for a region.
    If method_name is provided -> exact method. Else -> best (cheapest) method.
    """
    if method_name:
        sql = """
            SELECT name, carrier, cost, est_days_min, est_days_max
            FROM shipping_methods
            WHERE region IN (%s, 'World') AND name = %s
            LIMIT 1;
        """
        row = _fetch_one(sql, (region, method_name))
    else:
        sql = """
            SELECT name, carrier, cost, est_days_min, est_days_max
            FROM shipping_methods
            WHERE region IN (%s, 'World')
            ORDER BY cost ASC
            LIMIT 1;
        """
        row = _fetch_one(sql, (region,))
    return {"found": bool(row), "region": region, "estimate": row}


# ---- PAYMENT_RETRY tools -----------------------------------------------------

@tool
def tool_last_payment_status(order_id: int) -> Dict[str, Any]:
    """
    Get last payment attempt status for order_id.
    Returns: found, status, last_attempt(ISO), failure_code, failure_reason
    """
    sql = """
        SELECT status, last_attempt, failure_code, failure_reason
        FROM payments
        WHERE order_id = %s
        ORDER BY last_attempt DESC NULLS LAST
        LIMIT 1;
    """
    row = _fetch_one(sql, (order_id,))
    if not row:
        return {"found": False, "order_id": order_id}
    if row.get("last_attempt"):
        try:
            row["last_attempt"] = (
                row["last_attempt"].astimezone(timezone.utc).isoformat()
                if hasattr(row["last_attempt"], "astimezone")
                else str(row["last_attempt"])
            )
        except Exception:
            row["last_attempt"] = str(row["last_attempt"])
    return {"found": True, "order_id": order_id, **row}


@tool
def tool_can_retry_payment(order_id: int, cooldown_minutes: int = 30) -> Dict[str, Any]:
    """
    Decide if payment retry can be suggested based on last failed attempt time and cooldown.
    Returns: allowed(bool), reason, next_retry_after(ISO)
    """
    sql = """
        SELECT status, last_attempt
        FROM payments
        WHERE order_id = %s
        ORDER BY last_attempt DESC NULLS LAST
        LIMIT 1;
    """
    row = _fetch_one(sql, (order_id,))
    if not row:
        return {"allowed": False, "reason": "No payments found", "order_id": order_id}

    status = (row.get("status") or "").lower()
    last_attempt = row.get("last_attempt")
    now = datetime.now(timezone.utc)

    if status != "failed":
        return {"allowed": False, "reason": f"Status is '{status}' not 'Failed'."}

    if isinstance(last_attempt, datetime):
        next_time = last_attempt.astimezone(timezone.utc) + timedelta(minutes=cooldown_minutes)
    else:
        # If unknown, allow retry
        next_time = now

    allowed = now >= next_time
    return {
        "allowed": allowed,
        "reason": "Cooldown passed" if allowed else "Cooldown not passed",
        "next_retry_after": next_time.isoformat(),
        "order_id": order_id,
    }


@tool
def tool_payment_retry_steps(order_id: int, preferred_method: Optional[str] = None) -> Dict[str, Any]:
    """
    Return user-facing steps for retrying payment if last status is Failed.
    Reads payments table to tailor message.
    """
    last = tool_last_payment_status.invoke({"order_id": order_id})  # type: ignore
    if not last.get("found"):
        return {"ok": False, "order_id": order_id, "message": "No payment info found."}

    if (last.get("status") or "").lower() != "failed":
        return {"ok": False, "order_id": order_id, "message": "Payment is not in 'Failed' state."}

    steps = [
        "Откройте страницу заказа.",
        "Нажмите «Повторить платёж».",
        f"Выберите метод оплаты ({preferred_method or 'рекомендуется: CreditCard'}).",
        "Подтвердите оплату."
    ]
    return {
        "ok": True,
        "order_id": order_id,
        "steps": steps,
        "last_attempt": last.get("last_attempt"),
        "failure_code": last.get("failure_code"),
        "failure_reason": last.get("failure_reason"),
    }


# ---- RETURN_ISSUE tools ------------------------------------------------------

@tool
def tool_last_return_status(order_id: int) -> Dict[str, Any]:
    """
    Get last return request status for order_id with product title.
    Returns: found, status, request_date, product_title
    """
    sql = """
        SELECT r.status, r.request_date, p.title AS product_title
        FROM returns r
        LEFT JOIN products p ON p.product_id = r.product_id
        WHERE r.order_id = %s
        ORDER BY r.request_date DESC
        LIMIT 1;
    """
    row = _fetch_one(sql, (order_id,))
    if not row:
        return {"found": False, "order_id": order_id}
    # Normalize date to ISO string
    if row.get("request_date"):
        try:
            # date has no tz; render as ISO date
            row["request_date"] = str(row["request_date"])
        except Exception:
            row["request_date"] = str(row["request_date"])
    return {"found": True, "order_id": order_id, **row}


@tool
def tool_return_eligibility(order_id: int, policy_days: int = 14) -> Dict[str, Any]:
    """
    Check if order is still eligible for return based on Delivered event in shipment_events.
    Returns: eligible(bool), delivered_at(ISO|null), policy_days, days_since_delivery
    """
    # Find delivered timestamp by last Delivered event
    sql = """
        SELECT e.event_time
        FROM shipment_events e
        JOIN orders o ON o.tracking_no = e.tracking_no
        WHERE o.order_id = %s AND e.status ILIKE 'Delivered%%'
        ORDER BY e.event_time DESC
        LIMIT 1;
    """
    row = _fetch_one(sql, (order_id,))
    if not row or not row.get("event_time"):
        return {
            "eligible": False,
            "reason": "No Delivered event found.",
            "order_id": order_id,
            "policy_days": policy_days,
            "delivered_at": None,
        }

    delivered_at: datetime = row["event_time"]
    now = datetime.now(timezone.utc)
    days = (now - delivered_at.astimezone(timezone.utc)).days
    return {
        "eligible": days <= policy_days,
        "order_id": order_id,
        "policy_days": policy_days,
        "delivered_at": delivered_at.astimezone(timezone.utc).isoformat(),
        "days_since_delivery": days,
    }


@tool
def tool_request_return_label(order_id: int, email: str) -> Dict[str, Any]:
    """
    Stub: create a return label request (side-effect mocked).
    Returns: created(bool), order_id, email
    """
    # In real life: insert into return_labels queue and send email
    return {"created": True, "order_id": order_id, "email": email}


# ---- CUSTOMER-SPECIFIC tools (with injected customer_id) -------------------

@tool
def tool_get_my_orders(config: RunnableConfig) -> Dict[str, Any]:
    """
    Get all orders for the current customer.
    Returns: orders list with order_id, status, total_amount, order_date, tracking info
    """
    customer_id = config.get("configurable", {}).get("customer_id", 501)  # Default to Alice

    sql = """
        SELECT o.order_id, o.status, o.order_date, o.total_amount, o.currency,
               o.tracking_no, o.carrier, o.eta_date
        FROM orders o
        WHERE o.customer_id = %s
        ORDER BY o.order_date DESC;
    """
    orders = _fetch_all(sql, (customer_id,))

    # Normalize dates to ISO strings
    for order in orders:
        if order.get("order_date"):
            try:
                order["order_date"] = (
                    order["order_date"].astimezone(timezone.utc).isoformat()
                    if hasattr(order["order_date"], "astimezone")
                    else str(order["order_date"])
                )
            except Exception:
                order["order_date"] = str(order["order_date"])

        if order.get("eta_date"):
            try:
                order["eta_date"] = str(order["eta_date"])
            except Exception:
                order["eta_date"] = str(order["eta_date"])

    return {"customer_id": customer_id, "orders": orders, "count": len(orders)}


@tool
def tool_get_my_order_status(order_id: int, config: RunnableConfig) -> Dict[str, Any]:
    """
    Get order status for a specific order that belongs to the current customer.
    Returns: order details with current status and tracking info
    """
    customer_id = config.get("configurable", {}).get("customer_id", 501)  # Default to Alice

    sql = """
        SELECT o.order_id, o.status, o.order_date, o.total_amount, o.currency,
               o.tracking_no, o.carrier, o.eta_date, o.status_updated_at
        FROM orders o
        WHERE o.order_id = %s AND o.customer_id = %s
        LIMIT 1;
    """
    order = _fetch_one(sql, (order_id, customer_id))

    if not order:
        return {"found": False, "order_id": order_id, "message": "Заказ не найден или не принадлежит вам"}

    # Get latest shipment event if tracking number exists
    last_event = None
    if order.get("tracking_no"):
        evt_sql = """
            SELECT status, location, event_time, details
            FROM shipment_events
            WHERE tracking_no = %s
            ORDER BY event_time DESC
            LIMIT 1;
        """
        last_event = _fetch_one(evt_sql, (order["tracking_no"],))
        if last_event and last_event.get("event_time"):
            try:
                last_event["event_time"] = (
                    last_event["event_time"].astimezone(timezone.utc).isoformat()
                    if hasattr(last_event["event_time"], "astimezone")
                    else str(last_event["event_time"])
                )
            except Exception:
                last_event["event_time"] = str(last_event["event_time"])

    # Normalize dates
    for date_field in ["order_date", "status_updated_at"]:
        if order.get(date_field):
            try:
                order[date_field] = (
                    order[date_field].astimezone(timezone.utc).isoformat()
                    if hasattr(order[date_field], "astimezone")
                    else str(order[date_field])
                )
            except Exception:
                order[date_field] = str(order[date_field])

    if order.get("eta_date"):
        try:
            order["eta_date"] = str(order["eta_date"])
        except Exception:
            order["eta_date"] = str(order["eta_date"])

    return {"found": True, "customer_id": customer_id, **order, "latest_tracking": last_event}


@tool
def tool_get_my_payments(config: RunnableConfig) -> Dict[str, Any]:
    """
    Get payment status for all orders of the current customer.
    Returns: list of payments with status, method, and failure details if any
    """
    customer_id = config.get("configurable", {}).get("customer_id", 501)  # Default to Alice

    sql = """
        SELECT p.order_id, p.method, p.amount, p.currency, p.status,
               p.last_attempt, p.failure_code, p.failure_reason,
               o.order_date
        FROM payments p
        JOIN orders o ON o.order_id = p.order_id
        WHERE o.customer_id = %s
        ORDER BY p.last_attempt DESC;
    """
    payments = _fetch_all(sql, (customer_id,))

    # Normalize dates
    for payment in payments:
        for date_field in ["last_attempt", "order_date"]:
            if payment.get(date_field):
                try:
                    payment[date_field] = (
                        payment[date_field].astimezone(timezone.utc).isoformat()
                        if hasattr(payment[date_field], "astimezone")
                        else str(payment[date_field])
                    )
                except Exception:
                    payment[date_field] = str(payment[date_field])

    return {"customer_id": customer_id, "payments": payments, "count": len(payments)}


@tool
def tool_get_my_returns(config: RunnableConfig) -> Dict[str, Any]:
    """
    Get return requests for all orders of the current customer.
    Returns: list of returns with status and details
    """
    customer_id = config.get("configurable", {}).get("customer_id", 501)  # Default to Alice

    sql = """
        SELECT r.return_id, r.order_id, r.request_date, r.status,
               r.approved, r.refund_amount, r.currency, r.notes,
               p.title as product_title
        FROM returns r
        JOIN orders o ON o.order_id = r.order_id
        LEFT JOIN products p ON p.product_id = r.product_id
        WHERE o.customer_id = %s
        ORDER BY r.request_date DESC;
    """
    returns = _fetch_all(sql, (customer_id,))

    # Normalize dates
    for ret in returns:
        if ret.get("request_date"):
            try:
                ret["request_date"] = str(ret["request_date"])
            except Exception:
                ret["request_date"] = str(ret["request_date"])

    return {"customer_id": customer_id, "returns": returns, "count": len(returns)}