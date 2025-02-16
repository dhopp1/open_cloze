import pandas as pd
import plotly.express as px
import streamlit as st


def calc_stats():
    all_stats = (
        pd.read_csv(
            f"database/{st.session_state['user_id']}/progress.csv", parse_dates=["date"]
        )
        .loc[lambda x: x.language == st.session_state["selected_language"], :]
        .reset_index(drop=True)
    )
    stats = all_stats.loc[
        lambda x: (x.set == st.session_state["selected_set"]),
        :,
    ].reset_index(drop=True)

    all_sentences = pd.read_csv(
        f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv",
        parse_dates=["last_practiced"],
    )

    sentences = all_sentences.loc[
        lambda x: (x.set == st.session_state["selected_set"]), :
    ].reset_index(drop=True)

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
        stats["set_progress"] = stats["set_progress"].ffill()

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

    # overall stats
    overall_progress = (
        all_sentences.groupby(["set"])[["set", "last_practiced"]]
        .max()
        .reset_index(drop=True)
    )
    time_spent = (
        all_stats.groupby("set")
        .sum(numeric_only=True)
        .reset_index()[["set", "seconds"]]
    )
    overall_progress = overall_progress.merge(time_spent, on="set", how="left")

    set_progress = (
        all_stats.groupby("set")
        .max(numeric_only=True)
        .reset_index()[["set", "set_progress"]]
    )
    overall_progress = overall_progress.merge(set_progress, on="set", how="left")

    def get_time(x):
        try:
            return int(x)
        except:
            return 0

    overall_progress["Minutes studied"] = [
        get_time(_) for _ in (overall_progress["seconds"] / 60)
    ]

    all_sentences["been_studied"] = (all_sentences["n_right"] > 0).astype(int)
    sum_info = (
        all_sentences.groupby(["set"])[["set", "n_right", "n_wrong", "been_studied"]]
        .sum(numeric_only=True)
        .reset_index()
    )
    overall_progress = overall_progress.merge(sum_info, on="set", how="left")

    counts = (
        all_sentences.groupby(["set"])[["set", "n_right"]]
        .count()
        .drop(["set"], axis=1)
        .reset_index()
        .rename({"n_right": "Number of sentences"}, axis=1)
    )
    overall_progress = overall_progress.merge(counts, on="set", how="left")

    overall_progress["Wrong/right ratio"] = round(
        overall_progress["n_wrong"] / overall_progress["n_right"], 2
    )

    overall_progress["Avg times studied"] = round(
        overall_progress["n_right"] / overall_progress["Number of sentences"], 2
    )

    overall_progress["set_progress"] = [
        str(_) + "%" if not (pd.isna(_)) else "0%"
        for _ in round(overall_progress["set_progress"] * 100, 4)
    ]

    overall_progress["last_practiced"] = [
        str(_)[:10] if len(str(_)) > 3 else ""
        for _ in overall_progress["last_practiced"]
    ]

    # final columns
    overall_progress = overall_progress.loc[
        :,
        [
            "set",
            "set_progress",
            "been_studied",
            "Number of sentences",
            "Avg times studied",
            "Wrong/right ratio",
            "Minutes studied",
            "last_practiced",
        ],
    ]
    overall_progress = overall_progress.rename(
        columns={
            "set": "Set",
            "set_progress": "Progress",
            "been_studied": "Number studied",
            "last_practiced": "Last practiced",
        }
    )

    # display DF
    st.markdown("### Overall language progress")
    st.data_editor(
        overall_progress,
        hide_index=True,
    )
