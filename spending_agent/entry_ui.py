"""Streamlit entry workflow; parser and storage own all business rules."""

import sqlite3
from datetime import date
from decimal import Decimal

import streamlit as st

from .parser import parse_transaction


def _save_pending(store):
    # Consume before writing: a queued click or later rerun has no draft to save.
    draft = st.session_state.pop("pending_expense", None)
    if draft is None:
        return
    try:
        saved = store.create_transaction(**draft)
    except (ValueError, sqlite3.Error, OSError) as exc:
        st.session_state["pending_expense"] = draft
        st.session_state["entry_error"] = f"Not recorded: {exc}. Please review and try again."
        return
    st.session_state["last_recorded_expense"] = saved
    st.session_state.pop("entry_error", None)


def render_entry(store):
    with st.container(border=True):
        st.subheader("Tell me what you spent")
        st.caption("Try “Lunch 35 WeChat” or “Bought a coat for 699 yesterday”. I’ll show you the details before recording it.")
        with st.form("spending_message_form", clear_on_submit=True):
            message = st.text_input("Your spending message", placeholder="Lunch 35 WeChat", key="spending_message")
            submitted = st.form_submit_button("Review expense", type="primary")
        if submitted:
            # A new message replaces the previous draft, including on failure.
            st.session_state.pop("pending_expense", None)
            st.session_state.pop("last_recorded_expense", None)
            st.session_state.pop("entry_error", None)
            try:
                st.session_state["pending_expense"] = parse_transaction(message)
            except ValueError as exc:
                st.session_state["entry_error"] = f"I couldn’t safely read that expense. {exc} Try one expense, such as “Lunch 35 WeChat”."

        if st.session_state.get("entry_error"):
            st.error(st.session_state["entry_error"])
        draft = st.session_state.get("pending_expense")
        if draft:
            st.write("Here’s what I understood — not saved yet:")
            st.write(f"¥{Decimal(draft['amount']):,.2f} · {draft['category']} · {draft['transaction_date']}")
            st.text(f"Merchant: {draft['merchant'] or 'Not provided'}\n"
                    f"Payment: {draft['payment_method'] or 'Not provided'}\nNotes: {draft['notes']}")
            st.caption("To correct these details, submit a revised message above.")
            st.button("Record expense", key="record_expense", type="primary", on_click=_save_pending, args=(store,))
            st.button("Discard preview", key="discard_expense",
                      on_click=lambda: st.session_state.pop("pending_expense", None))

        saved = st.session_state.get("last_recorded_expense")
        if saved:
            day = date.fromisoformat(saved["transaction_date"])
            st.success(f"Recorded ¥{Decimal(saved['amount']):,.2f} · {saved['category']} · "
                       f"{saved['payment_method'] or 'Payment not provided'} · {day.strftime('%b')} {day.day}")
            st.caption(f"Transaction #{saved['id']} · {saved['transaction_date']} · Your overview below is up to date.")
