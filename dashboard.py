"""Run with: python -m streamlit run dashboard.py --server.address localhost"""

import sqlite3
from decimal import Decimal

import altair as alt
import streamlit as st

from spending_agent.analytics import summarize, spending_by, compare_periods, daily_spending
from spending_agent.rules import today
from spending_agent.entry_ui import render_entry
from spending_agent.demo import resolve_mode, session_store, reset_demo


def money(value):
    """Display formatting only; monetary calculations live in analytics.py."""
    return f"¥{Decimal(value):,.2f}"


def breakdown_chart(result, field, label):
    rows = [{label: row[field], "Amount": float(row["amount"]),
             "Exact amount": money(row["amount"]), "Share": f"{row['share_percent']}%"}
            for row in result["groups"]]
    chart = alt.Chart(alt.Data(values=rows)).mark_bar(color="#168477", cornerRadiusEnd=4).encode(
        x=alt.X("Amount:Q", title="Recorded spending (CNY)", axis=alt.Axis(format=",.0f")),
        y=alt.Y(f"{label}:N", sort="-x", title=None),
        tooltip=[alt.Tooltip(f"{label}:N"), alt.Tooltip("Exact amount:N"), alt.Tooltip("Share:N")],
    ).properties(height=max(150, len(rows) * 34))
    st.altair_chart(chart, width="stretch")


def main(mode=None):
    st.set_page_config(page_title="Cash Crash", page_icon="💳", layout="wide")
    mode = resolve_mode(mode)
    st.title("Cash Crash")
    st.subheader("Your AI-powered personal spending assistant")
    st.caption("Portfolio prototype · Uses transparent rule-based natural-language parsing, not an LLM or external AI API.")
    as_of = today()
    if mode == "demo":
        st.info("Demo Mode — Data in this session is temporary and does not contain real financial information.")
        st.caption("Fictional sample data + your session-only entries. Please try fictional expenses, not sensitive financial information.")
    else:
        st.warning("LOCAL PERSONAL MODE — Saved transactions persist on this computer. Do not deploy this mode publicly.")
    st.caption(f"Your recorded spending, at a glance · CNY · {as_of} · Shanghai time")
    with st.sidebar:
        st.header("Cash Crash")
        st.caption("PUBLIC DEMO MODE" if mode == "demo" else "LOCAL PERSONAL MODE")
        st.caption("A simple view of where your money goes.")
        days = st.selectbox("Trend window", [30, 90], format_func=lambda value: f"Last {value} days")
        st.button("Refresh data", width="stretch")  # A click reruns and rereads SQLite.
        if mode == "demo":
            st.button("Reset Demo", key="reset_demo", on_click=reset_demo, args=(st.session_state,), width="stretch")
            st.caption("Restores the fictional samples for your session only.")
        st.caption("Only recorded expenses are included. Missing entries can affect comparisons.")

    try:
        # No cache: each refresh reads one consistent snapshot for all components.
        store = session_store(st.session_state, mode, as_of)
        if mode == "demo":
            with st.expander("Try these examples"):
                st.code("Lunch 35 WeChat\nStarbucks 28 Alipay\nTaxi 46", language=None)
        render_entry(store)
        records = store.retrieve_transactions()
    except (sqlite3.Error, OSError) as exc:
        st.error("Unable to read the spending database. Check the file location and access permissions.")
        with st.expander("Error details"):
            st.text(str(exc))
        st.stop()

    daily = summarize(records, "today", as_of)
    weekly = summarize(records, "week", as_of)
    monthly = summarize(records, "month", as_of)
    comparison = compare_periods(records, "week", as_of)
    categories = spending_by(records, "category", "month", as_of)
    payments = spending_by(records, "payment_method", "month", as_of)
    trend = daily_spending(records, days, as_of)
    percent = comparison["change_percent"]
    change_text = "N/A" if percent is None else f"{Decimal(percent):+,.2f}%"
    if not records:
        st.info("No transactions yet. Tell me what you spent in the message box above to get started.")

    columns = st.columns(4)
    for column, label, result in zip(columns[:3], ("Today", "This week", "This month"),
                                     (daily, weekly, monthly)):
        with column.container(border=True):
            st.metric(label, money(result["total"]))
            st.caption(f"{result['transaction_count']} recorded transactions")
    with columns[3].container(border=True):
        st.metric("Week-over-week change", change_text)
        st.caption(f"Change: {money(comparison['change_amount'])}")
    current, previous = comparison["current_range"], comparison["previous_range"]
    st.caption(f"Weekly comparison: {current['start']} – {current['end']} versus "
               f"{previous['start']} – {previous['end']} (matching weekdays). "
               "N/A means prior-period spending was zero.")

    left, right = st.columns([1, 1.4])
    with left.container(border=True):
        st.subheader("Categories · this month")
        st.caption(f"{monthly['date_range']['start']} – {as_of}")
        if categories["groups"]:
            breakdown_chart(categories, "category", "Category")
        else:
            st.info("No spending recorded this month.")
    with right.container(border=True):
        st.subheader(f"Daily spending · last {days} days")
        st.caption("Daily totals in CNY. Days without recorded expenses appear as zero.")
        rows = [{"Date": row["date"], "Amount": float(row["amount"]),
                 "Exact amount": money(row["amount"])} for row in trend["days"]]
        chart = alt.Chart(alt.Data(values=rows)).mark_line(color="#168477", point=True).encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Amount:Q", title="Recorded spending (CNY)", scale=alt.Scale(zero=True)),
            tooltip=[alt.Tooltip("Date:T", format="%d %b %Y"), alt.Tooltip("Exact amount:N")],
        ).properties(height=270)
        st.altair_chart(chart, width="stretch")

    left, right = st.columns(2)
    with left.container(border=True):
        st.subheader("Payment methods · this month")
        if payments["groups"]:
            breakdown_chart(payments, "payment_method", "Payment method")
        else:
            st.info("No payment breakdown for this month yet.")
        st.caption("Unknown means a payment method was not provided.")
    with right.container(border=True):
        st.subheader("Spending insights")
        leaders = monthly["highest_spending_categories"]
        st.markdown("**Highest spending · this month**")
        st.write(f"{', '.join(leaders)} · {money(monthly['highest_category_amount'])} each"
                 if leaders else "No spending recorded this month.")
        increases = comparison["largest_increase_categories"]
        st.markdown("**Largest category increase · this week**")
        st.write(f"{', '.join(increases)} · +{money(comparison['largest_increase_amount'])} each"
                 if increases else "No category increased over the comparison period.")
        st.markdown("**Week over week**")
        st.write(f"{money(comparison['current_total'])} versus {money(comparison['previous_total'])} "
                 f"· change {money(comparison['change_amount'])} ({change_text})")
        st.caption("Increases are ranked by yuan change, not percentage. All tied categories are shown.")

    st.subheader("Recent transactions")
    st.caption("Latest 50 saved transactions by spending date, across all periods; future-dated entries are shown here but excluded from current totals.")
    if records:
        st.dataframe([
            {"ID": row["id"], "Date": row["transaction_date"], "Amount (CNY)": money(row["amount"]),
             "Category": row["category"], "Merchant": row["merchant"] or "—",
             "Payment method": row["payment_method"] or "Unknown", "Notes": row["notes"] or "—"}
            for row in records[:50]
        ], hide_index=True, width="stretch")
    else:
        st.caption("No transactions to display.")

    with st.expander("About Cash Crash"):
        st.write("Cash Crash converts natural-language spending entries into structured transaction data, performs automated spending analytics, and visualizes financial trends.")
        st.write("Technology stack: Python · Streamlit · SQLite · Natural-language parsing · Data validation · Financial analytics · Data visualization")
        st.caption("The current parser uses deterministic rules. No external LLM, API keys, bank connection or payment integration is used. This is a portfolio demo, not a production multi-user financial application.")


if __name__ == "__main__":
    main()
