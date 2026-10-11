"""
Plotly figure factories sharing one blue-free visual language.

Every colour comes from ``theme`` at call time, never at import time, so the
same factory renders correctly in both the dark and light palettes. Calling
``theme.apply(mode)`` before building figures is all that is needed to switch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import theme as T
from data_engine import MONTH_ORDER


def _rev_col(df: pd.DataFrame) -> str:
    return "Total Income (Ex GST)" if "Total Income (Ex GST)" in df.columns else "Total Income"


# ─────────────────────────────────────────────────────────────────────────────
def style(fig: go.Figure, height: int = 360, title: str | None = None,
          legend_top: bool = True, y_prefix: str | None = None,
          y_suffix: str | None = None) -> go.Figure:
    """Apply the shared dashboard styling to any figure."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=T.FONT_UI, color=T.TEXT_MUTED, size=11.5),
        margin=dict(l=14, r=14, t=54 if title else 26, b=12),
        hoverlabel=dict(bgcolor=T.HOVER_BG, bordercolor=T.HOVER_BORDER,
                        font=dict(family=T.FONT_UI, color=T.TEXT, size=12)),
        colorway=T.CHART_COLORS,
        separators=".,",
    )
    if title:
        fig.update_layout(title=dict(
            text=title, x=0.012, xanchor="left", y=0.955, yanchor="top",
            font=dict(family=T.FONT_UI, size=14.5, color=T.TEXT, weight=700)))
    if legend_top:
        fig.update_layout(legend=dict(
            orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)", font=dict(size=10.5, color=T.TEXT_MUTED),
            title_text=""))
    fig.update_xaxes(showgrid=False, zeroline=False,
                     linecolor=T.AXIS_LINE,
                     tickfont=dict(size=10.5, color=T.TEXT_FAINT),
                     title_font=dict(size=11, color=T.TEXT_FAINT))
    fig.update_yaxes(showgrid=True, gridcolor=T.GRID, gridwidth=1,
                     zeroline=False, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(size=10.5, color=T.TEXT_FAINT),
                     title_font=dict(size=11, color=T.TEXT_FAINT))
    if y_prefix:
        fig.update_yaxes(tickprefix=y_prefix)
    if y_suffix:
        fig.update_yaxes(ticksuffix=y_suffix)
    return fig


def empty(msg: str = "No data for the current selection", height: int = 360) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(color=T.TEXT_FAINT, size=13))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style(fig, height=height, legend_top=False)


# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def revenue_vs_transactions(pf: pd.DataFrame) -> go.Figure:
    """Combo: revenue bars with a transaction-count line on a secondary axis."""
    if pf.empty:
        return empty()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=pf["Period"], y=pf["Revenue"], name="Commission revenue",
        marker=dict(color=T.JADE, line=dict(width=0)), opacity=.85,
        hovertemplate="<b>%{x}</b><br>Revenue ₹%{y:,.0f}<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=pf["Period"], y=pf["Transactions"], name="Transactions",
        mode="lines+markers", line=dict(color=T.AMBER, width=2.6, shape="spline"),
        marker=dict(size=7, color=T.AMBER, line=dict(color=T.MARKER_EDGE, width=1.6)),
        hovertemplate="<b>%{x}</b><br>%{y:,} transactions<extra></extra>",
    ), secondary_y=True)
    style(fig, height=400, title="Commission revenue and transaction volume by period")
    fig.update_yaxes(title_text="Revenue", tickprefix="₹", secondary_y=False)
    fig.update_yaxes(title_text="Transactions", showgrid=False, secondary_y=True)
    fig.update_xaxes(tickangle=-35)
    return fig


def monthly_by_fy(pf: pd.DataFrame, value: str, title: str,
                  prefix: str | None = None) -> go.Figure:
    """Grouped bars comparing the same month across financial years."""
    if pf.empty:
        return empty()
    fig = px.bar(pf, x="Month", y=value, color="FY", barmode="group",
                 category_orders={"Month": MONTH_ORDER},
                 color_discrete_sequence=[T.JADE, T.VIOLET, T.AMBER, T.ROSE])
    fig.update_traces(marker_line_width=0,
                      hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra>%{fullData.name}</extra>")
    return style(fig, title=title, y_prefix=prefix)


def take_rate_trend(pf: pd.DataFrame) -> go.Figure:
    if pf.empty:
        return empty()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pf["Period"], y=pf["TakeRate"], mode="lines+markers", name="Take rate",
        line=dict(color=T.VIOLET, width=2.8, shape="spline"),
        marker=dict(size=7, color=T.VIOLET, line=dict(color=T.MARKER_EDGE, width=1.6)),
        fill="tozeroy", fillcolor=T.rgba(T.VIOLET, .13),
        hovertemplate="<b>%{x}</b><br>Take rate %{y:.2f}%<extra></extra>",
    ))
    avg = float(np.nanmean(pf["TakeRate"])) if pf["TakeRate"].notna().any() else 0
    fig.add_hline(y=avg, line=dict(color=T.AMBER, width=1.2, dash="dot"),
                  annotation_text=f"avg {avg:.2f}%", annotation_position="top left",
                  annotation_font=dict(color=T.AMBER, size=10.5))
    style(fig, title="Take rate trend  (revenue ÷ GMV)", y_suffix="%", legend_top=False)
    fig.update_xaxes(tickangle=-35)
    return fig


def avg_bid_trend(pf: pd.DataFrame) -> go.Figure:
    if pf.empty:
        return empty()
    fig = px.line(pf, x="Month", y="AvgBid", color="FY", markers=True,
                  category_orders={"Month": MONTH_ORDER},
                  color_discrete_sequence=[T.JADE, T.VIOLET, T.AMBER, T.ROSE])
    fig.update_traces(line=dict(width=2.6, shape="spline"),
                      marker=dict(size=7, line=dict(color=T.MARKER_EDGE, width=1.6)),
                      hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra>%{fullData.name}</extra>")
    return style(fig, title="Average bid value by month", y_prefix="₹")


def state_donut(df: pd.DataFrame) -> go.Figure:
    if "State" not in df.columns or df.empty:
        return empty()
    rev_c = _rev_col(df)
    g = (df.groupby("State")
           .agg(Transactions=("Final Bid Value", "size"), Revenue=(rev_c, "sum"))
           .reset_index().sort_values("Transactions", ascending=False))
    fig = go.Figure(go.Pie(
        labels=g["State"], values=g["Transactions"], hole=.62, sort=False,
        marker=dict(colors=T.CHART_COLORS[:len(g)],
                    line=dict(color=T.SURFACE_2, width=3)),
        textinfo="label+percent", textposition="outside",
        textfont=dict(size=11.5, color=T.TEXT),
        customdata=g[["Revenue"]].values,
        hovertemplate="<b>%{label}</b><br>%{value:,} transactions"
                      "<br>Revenue ₹%{customdata[0]:,.0f}<extra></extra>",
    ))
    total = int(g["Transactions"].sum())
    fig.add_annotation(text=f"<b>{total:,}</b><br><span style='font-size:10px'>TRANSACTIONS</span>",
                       x=.5, y=.5, showarrow=False,
                       font=dict(family=T.FONT_MONO, size=20, color=T.TEXT))
    return style(fig, title="Transaction mix by state", legend_top=False)


def state_performance(df: pd.DataFrame) -> go.Figure:
    """Horizontal bars: revenue per state with take rate annotated."""
    if "State" not in df.columns or df.empty:
        return empty()
    rev_c = _rev_col(df)
    g = (df.groupby("State")
           .agg(GMV=("Final Bid Value", "sum"), Revenue=(rev_c, "sum"),
                Transactions=("Final Bid Value", "size"))
           .reset_index())
    g["TakeRate"] = np.where(g["GMV"] > 0, g["Revenue"] / g["GMV"] * 100, 0)
    g = g.sort_values("Revenue")
    fig = go.Figure(go.Bar(
        x=g["Revenue"], y=g["State"], orientation="h",
        marker=dict(color=g["Revenue"], colorscale=T.SCALE_JADE, line=dict(width=0)),
        text=[f"₹{v/1e5:,.1f}L · {t:.2f}% take" for v, t in zip(g["Revenue"], g["TakeRate"])],
        textposition="outside", textfont=dict(size=11, color=T.TEXT_MUTED),
        customdata=g[["Transactions", "GMV", "TakeRate"]].values,
        hovertemplate="<b>%{y}</b><br>Revenue ₹%{x:,.0f}<br>GMV ₹%{customdata[1]:,.0f}"
                      "<br>%{customdata[0]:,} transactions"
                      "<br>Take rate %{customdata[2]:.2f}%<extra></extra>",
    ))
    style(fig, title="Commission revenue by state", legend_top=False)
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=14, r=110, t=54, b=12))
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID, tickprefix="₹")
    fig.update_yaxes(showgrid=False)
    return fig


def segment_split(df: pd.DataFrame) -> go.Figure:
    """Captive vs Non-Captive across the metrics that matter."""
    if "Seller Segment" not in df.columns or df.empty:
        return empty()
    rev_c = _rev_col(df)
    g = (df.groupby("Seller Segment")
           .agg(Transactions=("Final Bid Value", "size"),
                GMV=("Final Bid Value", "sum"),
                Revenue=(rev_c, "sum"),
                AvgBid=("Final Bid Value", "mean"),
                AvgCommission=(rev_c, "mean"))
           .reset_index())
    g["TakeRate"] = np.where(g["GMV"] > 0, g["Revenue"] / g["GMV"] * 100, 0)
    g["TxnShare"] = g["Transactions"] / g["Transactions"].sum() * 100

    metrics = [("TxnShare", "Share of transactions", "%"),
               ("AvgBid", "Avg. bid value", "₹"),
               ("AvgCommission", "Avg. commission", "₹"),
               ("TakeRate", "Take rate", "%")]
    fig = make_subplots(rows=1, cols=4, subplot_titles=[m[1] for m in metrics],
                        horizontal_spacing=.085)
    palette = {seg: T.CHART_COLORS[i] for i, seg in enumerate(g["Seller Segment"])}
    for ci, (col, _, unit) in enumerate(metrics, start=1):
        for _, row in g.iterrows():
            val = row[col]
            label = f"₹{val:,.0f}" if unit == "₹" else f"{val:.1f}%"
            fig.add_trace(go.Bar(
                x=[row["Seller Segment"]], y=[val], name=row["Seller Segment"],
                marker=dict(color=palette[row["Seller Segment"]], line=dict(width=0)),
                text=[label], textposition="outside",
                textfont=dict(size=10.5, color=T.TEXT_MUTED),
                showlegend=(ci == 1), legendgroup=row["Seller Segment"],
                hovertemplate=f"<b>%{{x}}</b><br>{label}<extra></extra>",
            ), row=1, col=ci)
    style(fig, height=340, title="Captive vs Non-Captive seller economics")
    for ann in fig.layout.annotations:
        ann.font = dict(size=11, color=T.TEXT_FAINT, family=T.FONT_UI)
    fig.update_yaxes(showticklabels=False, showgrid=False)
    fig.update_xaxes(tickfont=dict(size=10, color=T.TEXT_MUTED))
    fig.update_layout(bargap=.45)
    return fig


def make_treemap(df: pd.DataFrame, top: int = 18) -> go.Figure:
    if "Make" not in df.columns or df.empty:
        return empty(height=420)
    rev_c = _rev_col(df)
    g = (df.groupby("Make")
           .agg(Transactions=("Final Bid Value", "size"),
                GMV=("Final Bid Value", "sum"),
                Revenue=(rev_c, "sum"),
                AvgBid=("Final Bid Value", "mean"))
           .reset_index().sort_values("GMV", ascending=False).head(top))
    fig = go.Figure(go.Treemap(
        labels=g["Make"], parents=[""] * len(g), values=g["GMV"],
        marker=dict(colors=g["AvgBid"], colorscale=T.SCALE_TREEMAP,
                    line=dict(color=T.SURFACE, width=2)),
        texttemplate="<b>%{label}</b><br>₹%{value:,.0f}",
        textfont=dict(family=T.FONT_UI, size=12, color=T.TREEMAP_TEXT),
        customdata=g[["Transactions", "AvgBid", "Revenue"]].values,
        hovertemplate="<b>%{label}</b><br>GMV ₹%{value:,.0f}"
                      "<br>%{customdata[0]:,} transactions"
                      "<br>Avg. bid ₹%{customdata[1]:,.0f}"
                      "<br>Revenue ₹%{customdata[2]:,.0f}<extra></extra>",
        pathbar=dict(visible=False),
    ))
    style(fig, height=420, title="GMV concentration by make  (shade = avg. bid value)",
          legend_top=False)
    fig.update_layout(margin=dict(l=8, r=8, t=54, b=8))
    return fig


def top_models(df: pd.DataFrame, n: int = 12) -> go.Figure:
    if "Model" not in df.columns or df.empty:
        return empty(height=420)
    rev_c = _rev_col(df)
    g = (df.groupby("Model")
           .agg(Transactions=("Final Bid Value", "size"),
                AvgBid=("Final Bid Value", "mean"),
                Revenue=(rev_c, "sum"))
           .reset_index().sort_values("Transactions", ascending=False).head(n)
           .sort_values("Transactions"))
    fig = go.Figure(go.Bar(
        x=g["Transactions"], y=g["Model"], orientation="h",
        marker=dict(color=g["Transactions"], colorscale=T.SCALE_VIOLET, line=dict(width=0)),
        text=g["Transactions"], textposition="outside",
        textfont=dict(size=10.5, color=T.TEXT_MUTED),
        customdata=g[["AvgBid", "Revenue"]].values,
        hovertemplate="<b>%{y}</b><br>%{x:,} transactions"
                      "<br>Avg. bid ₹%{customdata[0]:,.0f}"
                      "<br>Revenue ₹%{customdata[1]:,.0f}<extra></extra>",
    ))
    style(fig, height=420, title=f"Top {n} models by volume", legend_top=False)
    fig.update_layout(margin=dict(l=14, r=52, t=54, b=12))
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=10.5, color=T.TEXT_MUTED))
    return fig


def price_band_chart(bands: pd.DataFrame) -> go.Figure:
    if bands.empty:
        return empty()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=bands["Band"].astype(str), y=bands["Transactions"], name="Transactions",
        marker=dict(color=bands["Transactions"], colorscale=T.SCALE_AMBER, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>%{y:,} transactions<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=bands["Band"].astype(str), y=bands["TakeRate"], name="Take rate",
        mode="lines+markers", line=dict(color=T.JADE, width=2.6, shape="spline"),
        marker=dict(size=7, color=T.JADE, line=dict(color=T.MARKER_EDGE, width=1.6)),
        hovertemplate="<b>%{x}</b><br>Take rate %{y:.2f}%<extra></extra>",
    ), secondary_y=True)
    style(fig, title="Volume and take rate by price band")
    fig.update_layout(coloraxis_showscale=False)
    fig.update_yaxes(title_text="Transactions", secondary_y=False)
    fig.update_yaxes(title_text="Take rate", ticksuffix="%", showgrid=False, secondary_y=True)
    return fig


def age_vs_value(df: pd.DataFrame) -> go.Figure:
    """Odometer against bid value, coloured by vehicle age."""
    need = {"Odometer", "Final Bid Value"}
    if not need <= set(df.columns) or df.empty:
        return empty()
    d = df.dropna(subset=["Odometer", "Final Bid Value"]).copy()
    if d.empty:
        return empty()
    if len(d) > 4000:
        d = d.sample(4000, random_state=7)
    if "Year" in d.columns and d["Year"].notna().any():
        d["Age"] = (2026 - d["Year"]).clip(lower=0, upper=30)
        color, cbar = d["Age"], "Age (yrs)"
    else:
        color, cbar = d["Final Bid Value"], "Bid"
    fig = go.Figure(go.Scattergl(
        x=d["Odometer"], y=d["Final Bid Value"], mode="markers",
        marker=dict(size=6, color=color, colorscale=T.SCALE_JADE, opacity=.72,
                    line=dict(width=0),
                    colorbar=dict(title=dict(text=cbar, font=dict(size=10, color=T.TEXT_FAINT)),
                                  thickness=9, len=.7, x=1.01,
                                  tickfont=dict(size=9.5, color=T.TEXT_FAINT))),
        customdata=d[[c for c in ("Make", "Model") if c in d.columns]].values
        if {"Make", "Model"} <= set(d.columns) else None,
        hovertemplate=("<b>%{customdata[0]} %{customdata[1]}</b><br>"
                       if {"Make", "Model"} <= set(d.columns) else "")
        + "Odometer %{x:,.0f} km<br>Bid ₹%{y:,.0f}<extra></extra>",
    ))
    style(fig, title="Odometer against realised bid value", legend_top=False)
    fig.update_xaxes(title_text="Odometer (km)", showgrid=True, gridcolor=T.GRID)
    fig.update_yaxes(title_text="Final bid value", tickprefix="₹")
    return fig


def pareto(perf: pd.DataFrame, label_col: str, count_col: str,
           title: str, n: int = 15) -> go.Figure:
    """Top-N contribution bars with a cumulative GMV share line."""
    if perf.empty:
        return empty(height=400)
    d = perf.sort_values("GMV", ascending=False).head(n).copy()
    d["Cumulative"] = d["GMVShare"].cumsum()
    short = d[label_col].astype(str).str.slice(0, 22)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=short, y=d["GMV"], name="GMV",
        marker=dict(color=d["GMV"], colorscale=T.SCALE_JADE, line=dict(width=0)),
        customdata=d[[count_col, "Commission", "TakeRate"]].values,
        hovertemplate="<b>%{x}</b><br>GMV ₹%{y:,.0f}"
                      "<br>%{customdata[0]:,} deals"
                      "<br>Commission ₹%{customdata[1]:,.0f}"
                      "<br>Take rate %{customdata[2]:.2f}%<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=short, y=d["Cumulative"], name="Cumulative share of GMV",
        mode="lines+markers", line=dict(color=T.AMBER, width=2.4, shape="spline"),
        marker=dict(size=6, color=T.AMBER, line=dict(color=T.MARKER_EDGE, width=1.4)),
        hovertemplate="<b>%{x}</b><br>Cumulative %{y:.1f}% of GMV<extra></extra>",
    ), secondary_y=True)
    style(fig, height=400, title=title)
    fig.update_layout(coloraxis_showscale=False)
    fig.update_xaxes(tickangle=-40, tickfont=dict(size=9.5))
    fig.update_yaxes(title_text="GMV", tickprefix="₹", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative", ticksuffix="%", range=[0, 105],
                     showgrid=False, secondary_y=True)
    return fig


def cohort_heatmap(df: pd.DataFrame, index: str, title: str) -> go.Figure:
    """Revenue heatmap of a dimension against period."""
    if index not in df.columns or "Period" not in df.columns or df.empty:
        return empty(height=380)
    rev_c = _rev_col(df)
    piv = (df.pivot_table(index=index, columns="Period", values=rev_c,
                          aggfunc="sum", observed=False)
             .fillna(0))
    if piv.empty:
        return empty(height=380)
    sort_keys = [c for c in ("FY", "_month_idx") if c in df.columns]
    ordered_periods = (df.sort_values(sort_keys)["Period"].unique() if sort_keys
                       else piv.columns.tolist())
    cols = [c for c in ordered_periods if c in piv.columns]
    piv = piv[cols]
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index][:14]
    fig = go.Figure(go.Heatmap(
        z=piv.values, x=piv.columns.tolist(), y=piv.index.tolist(),
        colorscale=T.SCALE_JADE, showscale=True,
        colorbar=dict(thickness=9, len=.75,
                      tickfont=dict(size=9.5, color=T.TEXT_FAINT),
                      tickprefix="₹"),
        hovertemplate="<b>%{y}</b><br>%{x}<br>Revenue ₹%{z:,.0f}<extra></extra>",
        xgap=2, ygap=2,
    ))
    style(fig, height=380, title=title, legend_top=False)
    fig.update_xaxes(tickangle=-35, showgrid=False)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=10.5, color=T.TEXT_MUTED))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def quality_gauge(score: float, accent: str) -> go.Figure:
    color = T.ACCENTS.get(accent, T.ACCENTS["jade"])["solid"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(suffix="%", font=dict(family=T.FONT_MONO, size=40, color=T.TEXT)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor=T.GAUGE_TICK,
                      tickfont=dict(size=9.5, color=T.TEXT_FAINT)),
            bar=dict(color=color, thickness=.28),
            bgcolor=T.GAUGE_BG,
            borderwidth=0,
            steps=[
                dict(range=[0, 70], color=T.STEP_BAD),
                dict(range=[70, 85], color=T.STEP_MID),
                dict(range=[85, 100], color=T.STEP_GOOD),
            ],
            threshold=dict(line=dict(color=T.TEXT, width=2), thickness=.8, value=95),
        ),
    ))
    fig.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=24, r=24, t=14, b=6),
                      font=dict(family=T.FONT_UI, color=T.TEXT_MUTED))
    return fig


def dimension_radar(dims: dict) -> go.Figure:
    labels = list(dims.keys()) + [list(dims.keys())[0]]
    vals = list(dims.values()) + [list(dims.values())[0]]
    fig = go.Figure(go.Scatterpolar(
        r=vals, theta=labels, fill="toself",
        fillcolor=T.rgba(T.JADE, .16),
        line=dict(color=T.JADE, width=2.4),
        marker=dict(size=7, color=T.JADE, line=dict(color=T.MARKER_EDGE, width=1.5)),
        hovertemplate="<b>%{theta}</b><br>%{r:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=52, r=52, t=26, b=26), showlegend=False,
        font=dict(family=T.FONT_UI, color=T.TEXT_MUTED, size=10.5),
        polar=dict(
            bgcolor=T.POLAR_BG,
            radialaxis=dict(range=[0, 100], showline=False, gridcolor=T.AXIS_LINE,
                            tickfont=dict(size=8.5, color=T.TEXT_FAINT), angle=90,
                            tickvals=[25, 50, 75, 100]),
            angularaxis=dict(gridcolor=T.AXIS_LINE,
                             tickfont=dict(size=10.5, color=T.TEXT_MUTED)),
        ),
    )
    return fig


def null_profile(health: pd.DataFrame) -> go.Figure:
    if health.empty:
        return empty(height=340)
    d = health.sort_values("Populated %")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["Populated %"], y=d["Column"], orientation="h", name="Populated",
        marker=dict(color=d["Populated %"], colorscale=T.SCALE_JADE, line=dict(width=0)),
        text=[f"{v:.1f}%" for v in d["Populated %"]], textposition="outside",
        textfont=dict(size=10.5, color=T.TEXT_MUTED),
        customdata=d[["Nulls", "Distinct", "Type"]].values,
        hovertemplate="<b>%{y}</b><br>Populated %{x:.2f}%"
                      "<br>%{customdata[0]:,} nulls"
                      "<br>%{customdata[1]:,} distinct values"
                      "<br>Type %{customdata[2]}<extra></extra>",
    ))
    style(fig, height=max(320, 30 * len(d)), title="Field population rate", legend_top=False)
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=14, r=64, t=54, b=12))
    fig.update_xaxes(range=[0, 108], showgrid=True, gridcolor=T.GRID, ticksuffix="%")
    fig.update_yaxes(showgrid=False, tickfont=dict(size=10.5, color=T.TEXT_MUTED))
    return fig


def missingness_map(df: pd.DataFrame, max_cols: int = 900) -> go.Figure:
    work = df.drop(columns=[c for c in ("_month_idx", "Period") if c in df.columns])
    if work.empty:
        return empty(height=320)
    m = work.isna().astype(int)
    if len(m) > max_cols:
        step = int(np.ceil(len(m) / max_cols))
        m = m.iloc[::step]
    fig = go.Figure(go.Heatmap(
        z=m.T.values, y=m.columns.tolist(),
        colorscale=[[0, T.PRESENT_TINT], [1, T.ROSE]],
        showscale=False, xgap=0, ygap=1.5,
        hovertemplate="<b>%{y}</b><br>row ~%{x}<br>%{z}<extra></extra>",
    ))
    style(fig, height=max(300, 26 * len(m.columns)),
          title="Missing-value map  (rose = null, jade = present)", legend_top=False)
    fig.update_xaxes(showticklabels=False, showgrid=False, title_text="records (sampled in order)")
    fig.update_yaxes(showgrid=False, tickfont=dict(size=10, color=T.TEXT_MUTED))
    return fig


def outlier_box(df: pd.DataFrame, cols: list[str]) -> go.Figure:
    cols = [c for c in cols if c in df.columns and df[c].notna().any()]
    if not cols:
        return empty(height=340)
    fig = make_subplots(rows=1, cols=len(cols), subplot_titles=cols,
                        horizontal_spacing=.09)
    for i, c in enumerate(cols, start=1):
        fig.add_trace(go.Box(
            y=df[c].dropna(), name=c, boxpoints="outliers",
            marker=dict(color=T.CHART_COLORS[(i - 1) % len(T.CHART_COLORS)],
                        outliercolor=T.ROSE, size=4, opacity=.7),
            line=dict(width=1.6), fillcolor=T.BOX_FILL,
            hovertemplate="%{y:,.0f}<extra></extra>",
        ), row=1, col=i)
    style(fig, height=350, title="Numeric distributions and IQR outliers", legend_top=False)
    fig.update_layout(showlegend=False)
    for ann in fig.layout.annotations:
        ann.font = dict(size=11, color=T.TEXT_FAINT, family=T.FONT_UI)
    fig.update_xaxes(showticklabels=False)
    return fig
