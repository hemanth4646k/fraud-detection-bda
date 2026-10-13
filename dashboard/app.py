from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fraud_detection.config import get_settings
from fraud_detection.dashboard_data import load_dashboard_frames


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
COLORS = {
    "critical": "#FF4B4B",
    "high": "#FF8C42",
    "medium": "#FFD166",
    "monitor": "#4CC9F0",
    "accent": "#6C63FF",
    "green": "#2ECC71",
    "text": "#E6E8EF",
    "muted": "#8B90A0",
}

ALERT_ORDER = ["critical", "high", "medium", "monitor"]


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        /* Hero header */
        .hero {
            padding: 1.4rem 1.6rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #2A0B4E 0%, #6C63FF 55%, #FF4B4B 130%);
            margin-bottom: 1.2rem;
            box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
        }
        .hero h1 { color: #FFFFFF; font-size: 2.1rem; font-weight: 800; margin: 0; letter-spacing: -0.5px; }
        .hero p { color: rgba(255, 255, 255, 0.85); margin: 0.35rem 0 0 0; font-size: 0.95rem; }
        .hero .stamp { color: rgba(255, 255, 255, 0.65); font-size: 0.78rem; margin-top: 0.5rem; }

        /* KPI cards */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.4rem 0 1.2rem 0;
        }
        .kpi-card {
            background: #1A1D29;
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-left: 4px solid var(--accent, #6C63FF);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 10px 24px rgba(0, 0, 0, 0.4); }
        .kpi-card .kpi-label { color: #8B90A0; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
        .kpi-card .kpi-value { color: #FAFAFA; font-size: 1.9rem; font-weight: 800; margin-top: 0.35rem; line-height: 1.1; }
        .kpi-card .kpi-delta { font-size: 0.8rem; font-weight: 600; margin-top: 0.3rem; }
        .kpi-delta.up   { color: #FF6B6B; }
        .kpi-delta.down { color: #2ECC71; }
        .kpi-delta.flat { color: #8B90A0; }

        /* Section headers */
        .section-title { font-size: 1.05rem; font-weight: 700; color: #FAFAFA; margin: 0.6rem 0 0.2rem 0; }
        .section-sub { color: #8B90A0; font-size: 0.85rem; margin-bottom: 0.6rem; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 0.5rem 1.1rem; font-weight: 600; }

        /* Alert level badges */
        .badge { display: inline-block; padding: 0.12rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; text-transform: capitalize; color: #0E1117; }
        .badge-critical { background: #FF4B4B; }
        .badge-high     { background: #FF8C42; }
        .badge-medium   { background: #FFD166; }
        .badge-monitor  { background: #4CC9F0; }

        hr.soft { border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 1rem 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.00%"
    return f"{(numerator / denominator) * 100:.2f}%"


def precision_recall_from_stream(predictions: pd.DataFrame) -> tuple[float | None, float | None]:
    if predictions.empty or {"actual_label", "predicted_label"} - set(predictions.columns):
        return None, None

    actual_positive = predictions["actual_label"].astype(int) == 1
    predicted_positive = predictions["predicted_label"].astype(int) == 1
    true_positive = int((actual_positive & predicted_positive).sum())
    predicted_positive_count = int(predicted_positive.sum())
    actual_positive_count = int(actual_positive.sum())

    precision = true_positive / predicted_positive_count if predicted_positive_count else None
    recall = true_positive / actual_positive_count if actual_positive_count else None
    return precision, recall


def badge_for(level: str) -> str:
    level = str(level).lower()
    if level not in ALERT_ORDER:
        level = "monitor"
    return f'<span class="badge badge-{level}">{level}</span>'


def styled_alerts_table(alerts_view: pd.DataFrame) -> None:
    """Render the recent high-risk transactions table with an alert-level badge column."""
    display_columns = [
        column
        for column in [
            "processed_at",
            "alert_level",
            "transaction_id",
            "merchant_category",
            "channel",
            "Amount",
            "risk_score",
            "predicted_label",
            "actual_label",
            "city",
            "country_code",
        ]
        if column in alerts_view.columns
    ]

    table = alerts_view.sort_values("risk_score", ascending=False)[display_columns].head(25).copy()

    if "alert_level" in table.columns:
        table["alert_level"] = table["alert_level"].map(badge_for)
    if "Amount" in table.columns:
        table["Amount"] = table["Amount"].map(lambda v: f"${v:,.2f}")
    if "risk_score" in table.columns:
        table["risk_score"] = table["risk_score"].map(lambda v: f"{v:.4f}")
    if "processed_at" in table.columns:
        table["processed_at"] = pd.to_datetime(table["processed_at"], errors="coerce").dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    st.markdown(
        table.to_html(escape=False, index=False)
        + """
        <style>
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        thead th {
            text-align: left; color: #8B90A0; text-transform: uppercase;
            font-size: 0.72rem; letter-spacing: 0.5px;
            border-bottom: 1px solid rgba(255,255,255,0.12); padding: 0.5rem 0.6rem;
        }
        tbody td { padding: 0.5rem 0.6rem; border-bottom: 1px solid rgba(255,255,255,0.06); color: #E6E8EF; }
        tbody tr:hover { background: rgba(108, 99, 255, 0.08); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def altair_bar(df: pd.DataFrame, x_field: str, y_field: str, color: str, height: int = 250) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(f"{x_field}:N", sort="-y", title=None),
            y=alt.Y(f"{y_field}:Q", title=None),
            color=alt.value(color),
            tooltip=[x_field, y_field],
        )
        .properties(height=height)
        .configure_view(strokeOpacity=0)
        .configure_axis(labelColor="#8B90A0", titleColor="#8B90A0")
    )



# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
def build_charts(frame: pd.DataFrame) -> dict[str, alt.Chart]:
    charts: dict[str, alt.Chart] = {}

    # Risk trend over time (area chart)
    if not frame.empty and "processed_at" in frame.columns and "risk_score" in frame.columns:
        trend = (
            frame.dropna(subset=["processed_at"])
            .set_index("processed_at")["risk_score"]
            .resample("1min")
            .mean()
            .dropna()
            .rename("avg_risk")
            .reset_index()
        )
        if not trend.empty:
            charts["trend"] = (
                alt.Chart(trend)
                .mark_area(
                    line={"color": COLORS["accent"]},
                    color=alt.Gradient(
                        gradient="linear",
                        x1=1, x2=1, y1=1, y2=0,
                        stops=[
                            alt.GradientStop(color="rgba(108,99,255,0.45)", offset=0),
                            alt.GradientStop(color="rgba(108,99,255,0.0)", offset=1),
                        ],
                    ),
                )
                .encode(
                    x=alt.X("processed_at:T", title=None),
                    y=alt.Y("avg_risk:Q", title="Avg risk"),
                    tooltip=["processed_at:T", "avg_risk:Q"],
                )
                .properties(height=280)
                .interactive()
                .configure_view(strokeOpacity=0)
                .configure_axis(labelColor="#8B90A0", titleColor="#8B90A0")
            )

    # Risk score distribution (histogram)
    if not frame.empty and "risk_score" in frame.columns:
        charts["distribution"] = (
            alt.Chart(frame)
            .mark_bar(color=COLORS["monitor"], cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
            .encode(
                x=alt.X("risk_score:Q", bin=alt.Bin(maxbins=25), title="Risk score"),
                y=alt.Y("count():Q", title="Transactions"),
                tooltip=[alt.Tooltip("count():Q", title="Count")],
            )
            .properties(height=280)
            .configure_view(strokeOpacity=0)
            .configure_axis(labelColor="#8B90A0", titleColor="#8B90A0")
        )

    # Categorical breakdowns (bar)
    categorical = [
        ("merchant_category", "merchant", COLORS["high"]),
        ("channel", "channel", COLORS["accent"]),
        ("country_code", "country", COLORS["monitor"]),
    ]
    for col, key, color in categorical:
        if not frame.empty and col in frame.columns:
            counts = (
                frame[col].fillna("unknown").value_counts().rename_axis(col).reset_index(name="count").head(10)
            )
            charts[key] = altair_bar(counts, col, "count", color, height=250)

    # Alert-level breakdown (donut)
    if not frame.empty and "alert_level" in frame.columns:
        levels = frame["alert_level"].fillna("monitor").value_counts().rename_axis("alert_level").reset_index(name="count")
        charts["levels"] = (
            alt.Chart(levels)
            .mark_arc(innerRadius=55, cornerRadius=3)
            .encode(
                theta="count:Q",
                color=alt.Color(
                    "alert_level:N",
                    scale=alt.Scale(
                        domain=ALERT_ORDER,
                        range=[COLORS["critical"], COLORS["high"], COLORS["medium"], COLORS["monitor"]],
                    ),
                    legend=alt.Legend(title="Level", labelColor="#E6E8EF", titleColor="#8B90A0"),
                ),
                tooltip=["alert_level", "count"],
            )
            .properties(height=280)
        )

    # Amount vs risk scatter (sampled)
    if not frame.empty and {"Amount", "risk_score"} <= set(frame.columns):
        sample = frame[["Amount", "risk_score", "alert_level"]].dropna()
        if len(sample) > 1500:
            sample = sample.sample(1500, random_state=1)
        charts["scatter"] = (
            alt.Chart(sample)
            .mark_circle(size=45, opacity=0.55)
            .encode(
                x=alt.X("Amount:Q", title="Amount"),
                y=alt.Y("risk_score:Q", title="Risk score"),
                color=alt.Color(
                    "alert_level:N",
                    scale=alt.Scale(
                        domain=ALERT_ORDER,
                        range=[COLORS["critical"], COLORS["high"], COLORS["medium"], COLORS["monitor"]],
                    ),
                    legend=None,
                ),
                tooltip=["Amount", "risk_score", "alert_level"],
            )
            .properties(height=300)
            .interactive()
            .configure_view(strokeOpacity=0)
            .configure_axis(labelColor="#8B90A0", titleColor="#8B90A0")
        )

    return charts



# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Fraud Detection Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_custom_css()

settings = get_settings()
predictions, alerts = load_dashboard_frames(settings)

st.markdown(
    f"""
    <div class="hero">
        <h1>🛡️ Fraud Detection Command Center</h1>
        <p>Kafka → Spark Structured Streaming → parquet + MinIO + optional Snowflake</p>
        <div class="stamp">Last refreshed: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar controls
threshold = st.sidebar.slider(
    "Visible alert threshold",
    min_value=0.0,
    max_value=1.0,
    value=float(settings.min_alert_probability),
    step=0.05,
)
alert_levels_selected = st.sidebar.multiselect(
    "Alert levels",
    options=ALERT_ORDER,
    default=ALERT_ORDER,
)
st.sidebar.caption("Use the browser refresh button after new micro-batches arrive.")

# Empty state
if predictions.empty:
    st.warning(
        "No scored transactions found yet. Start the streaming job and the Kafka producer, then refresh."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Data prep
# ---------------------------------------------------------------------------
if "processed_at" in predictions.columns:
    predictions = predictions.sort_values("processed_at")
elif "event_ts" in predictions.columns:
    predictions = predictions.sort_values("event_ts")

alerts_view = alerts.copy()
if not alerts_view.empty and "risk_score" in alerts_view.columns:
    alerts_view = alerts_view[alerts_view["risk_score"] >= threshold]
if not alerts_view.empty and "alert_level" in alerts_view.columns:
    alerts_view = alerts_view[alerts_view["alert_level"].isin(alert_levels_selected)]

# KPI computations
total_transactions = int(len(predictions))
predicted_fraud = int(predictions["predicted_label"].sum()) if "predicted_label" in predictions.columns else 0
actual_fraud = int(predictions["actual_label"].sum()) if "actual_label" in predictions.columns else 0
average_risk = float(predictions["risk_score"].mean()) if "risk_score" in predictions.columns else 0.0
precision, recall = precision_recall_from_stream(predictions)

critical_count = 0
if not alerts_view.empty and "alert_level" in alerts_view.columns:
    critical_count = int((alerts_view["alert_level"] == "critical").sum())

pr_text = (
    f"{precision:.2%} / {recall:.2%}"
    if precision is not None and recall is not None
    else "Unavailable"
)

# KPI cards
kpi_specs = [
    ("Transactions scored", f"{total_transactions:,}", None, "flat", COLORS["accent"]),
    ("Predicted fraud", f"{predicted_fraud:,}",
     format_ratio(predicted_fraud, total_transactions) + " of total",
     "up" if predicted_fraud else "flat", COLORS["critical"]),
    ("Actual fraud", f"{actual_fraud:,}",
     format_ratio(actual_fraud, total_transactions) + " of total",
     "up" if actual_fraud else "flat", COLORS["high"]),
    ("Critical alerts", f"{critical_count:,}",
     format_ratio(critical_count, max(total_transactions, 1)) + " of total",
     "up" if critical_count else "flat", COLORS["critical"]),
    ("Average risk", f"{average_risk:.3f}", None, "flat", COLORS["monitor"]),
    ("Precision / Recall", pr_text, None, "flat", COLORS["green"]),
]
cards_html = '<div class="kpi-grid">'
for label, value, delta, kind, accent in kpi_specs:
    delta_html = f'<div class="kpi-delta {kind}">{delta}</div>' if delta else ""
    cards_html += (
        f'<div class="kpi-card" style="--accent: {accent}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )
cards_html += "</div>"
st.markdown(cards_html, unsafe_allow_html=True)

charts = build_charts(predictions)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_analytics, tab_alerts, tab_model = st.tabs(
    ["📊 Overview", "📈 Analytics", "🚨 Alerts feed", "🧠 Model performance"]
)

# --- Overview ---
with tab_overview:
    st.markdown('<div class="section-title">Alert level summary</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Distribution of scored alerts by severity (respects the sidebar filters).</div>',
        unsafe_allow_html=True,
    )
    if "levels" in charts:
        left, right = st.columns([1, 1.4])
        with left:
            st.altair_chart(charts["levels"], width="stretch")
        with right:
            if "merchant" in charts:
                st.markdown('<div class="section-title">Alerts by merchant category</div>', unsafe_allow_html=True)
                st.altair_chart(charts["merchant"], width="stretch")
    else:
        st.info("No alert rows match the current filters yet.")

# --- Analytics ---
with tab_analytics:
    st.markdown('<div class="section-title">Risk trend &amp; distribution</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if "trend" in charts:
            st.altair_chart(charts["trend"], width="stretch")
        else:
            st.info("Not enough timestamped batches yet to draw a trend.")
    with c2:
        if "distribution" in charts:
            st.altair_chart(charts["distribution"], width="stretch")
        else:
            st.info("Risk scores unavailable.")

    st.markdown('<hr class="soft">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Breakdowns</div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    for col, key in zip((b1, b2, b3), ("channel", "country", "merchant")):
        with col:
            if key in charts:
                st.altair_chart(charts[key], width="stretch")
            else:
                st.info("No data.")

    if "scatter" in charts:
        st.markdown('<hr class="soft">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Amount vs. risk</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">Each point is a scored transaction (sampled for performance).</div>',
            unsafe_allow_html=True,
        )
        st.altair_chart(charts["scatter"], width="stretch")

# --- Alerts feed ---
with tab_alerts:
    st.markdown('<div class="section-title">Recent high-risk transactions</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Top 25 by risk score. Filtered by the sidebar threshold and alert levels.</div>',
        unsafe_allow_html=True,
    )
    if alerts_view.empty:
        st.info("No alerts match the selected threshold and alert levels yet.")
    else:
        styled_alerts_table(alerts_view)

# --- Model performance ---
with tab_model:
    st.markdown('<div class="section-title">Streaming model performance</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Computed live from the scored prediction stream.</div>',
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Precision", f"{precision:.2%}" if precision is not None else "N/A")
    m2.metric("Recall", f"{recall:.2%}" if recall is not None else "N/A")
    current_threshold = (
        float(predictions["model_threshold"].iloc[-1])
        if "model_threshold" in predictions.columns and not predictions.empty
        else float(settings.min_alert_probability)
    )
    m3.metric("Model threshold", f"{current_threshold:.4f}")
    m4.metric("Visible threshold", f"{threshold:.2f}")

    if {"actual_label", "predicted_label"} <= set(predictions.columns):
        tp = int(((predictions["actual_label"] == 1) & (predictions["predicted_label"] == 1)).sum())
        fp = int(((predictions["actual_label"] == 0) & (predictions["predicted_label"] == 1)).sum())
        fn = int(((predictions["actual_label"] == 1) & (predictions["predicted_label"] == 0)).sum())
        tn = int(((predictions["actual_label"] == 0) & (predictions["predicted_label"] == 0)).sum())
        cm = pd.DataFrame(
            {"Predicted fraud": [tp, fp], "Predicted legit": [fn, tn]},
            index=["Actual fraud", "Actual legit"],
        )
        st.markdown('<hr class="soft">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Confusion matrix (streamed counts)</div>', unsafe_allow_html=True)
        st.table(cm)

