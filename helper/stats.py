import pandas as pd
import plotly.express as px
import streamlit as st


def calc_stats():
    stats = (
        pd.read_csv(
            f"database/{st.session_state['user_id']}/progress.csv", parse_dates=["date"]
        )
        .loc[
            lambda x: (x.set == st.session_state["selected_set"])
            & (x.language == st.session_state["selected_language"]),
            :,
        ]
        .reset_index(drop=True)
    )

    sentences = (
        pd.read_csv(
            f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv"
        )
        .loc[lambda x: (x.set == st.session_state["selected_set"]), :]
        .reset_index(drop=True)
    )

    if len(stats) > 0:
        progress_value = stats.set_progress.max()
    else:
        progress_value = 0.0

    st.progress(
        progress_value,
        text=f"**Set progress ({round(progress_value * 100, 6)}%, {int(progress_value * len(sentences))}  of {len(sentences):,} sentences)**",
    )

    # date range
    if len(stats) > 0:
        min_date = stats.date.min()
        max_date = stats.date.max()
    else:
        min_date = "today"
        max_date = "today"

    st.session_state["date_range"] = st.date_input(
        label="Date range",
        value=(min_date, max_date),
        format="DD.MM.YYYY",
    )

    if (len(st.session_state["date_range"]) == 2) and len(
        stats
    ) > 0:  # for not throwing an error while changing dates
        try:
            stats = stats.loc[
                lambda x: (x.language == st.session_state["selected_language"])
                & (
                    x.date.dt.strftime("%Y-%m-%d")
                    >= str(st.session_state["date_range"][0])
                )
                & (
                    x.date.dt.strftime("%Y-%m-%d")
                    <= str(st.session_state["date_range"][1])
                )
                & (x.set == st.session_state["selected_set"]),
                :,
            ].reset_index(drop=True)
        except:
            pass

        # time aggregation select box
        st.session_state["stat_time_agg"] = st.selectbox(
            "Select time aggregation",
            options=["daily", "weekly", "monthly", "yearly"],
            index=0,
        )

        # converting to pandas time agg
        if st.session_state["stat_time_agg"] == "daily":
            time_agg = "D"
        elif st.session_state["stat_time_agg"] == "weekly":
            time_agg = "W"
        elif st.session_state["stat_time_agg"] == "monthly":
            time_agg = "M"
        elif st.session_state["stat_time_agg"] == "yearly":
            time_agg = "Y"

        stats = (
            stats.set_index("date")
            .resample(time_agg)
            .agg(
                {
                    "set_progress": "max",
                    "n_sentences": "sum",
                    "n_wrong": "sum",
                    "seconds": "sum",
                }
            )
            .reset_index()
        )

        # linegraph of number of sentences studied
        fig = px.line(
            stats,
            x="date",
            y="n_sentences",
        )

        fig.update_layout(
            yaxis_title="",
            xaxis_title="",
            title="Number of sentences studied",
        )

        st.plotly_chart(fig, height=450, use_container_width=True)

        # linegraph of time spent
        stats["minutes"] = stats["seconds"] / 60
        fig = px.line(
            stats,
            x="date",
            y="minutes",
        )

        fig.update_layout(
            yaxis_title="",
            xaxis_title="",
            title="Minutes spent studying",
        )

        st.plotly_chart(fig, height=450, use_container_width=True)

        # linegraph of set progress
        fig = px.line(
            stats,
            x="date",
            y="set_progress",
        )

        fig.update_layout(
            yaxis_title="",
            xaxis_title="",
            title="Set progress over time",
        )
        fig.update_yaxes(tickformat=".6%")

        st.plotly_chart(fig, height=450, use_container_width=True)

        # linegraph of correct ratio
        stats["ratio"] = stats["n_wrong"] / stats["n_sentences"]
        stats = stats.fillna(0)
        fig = px.line(
            stats,
            x="date",
            y="ratio",
        )

        fig.update_layout(
            yaxis_title="",
            xaxis_title="",
            title="Wrong/Right ratio (0 = no mistakes, 2 = 2 mistakes for every correct answer)",
        )

        st.plotly_chart(fig, height=450, use_container_width=True)
