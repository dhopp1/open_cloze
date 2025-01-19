import os
import pandas as pd
import streamlit as st
import time

from helper.questions import setup_round


def ui_tab():
    "tab title and icon"
    st.set_page_config(
        page_title="Open Cloze",
        page_icon="https://www.svgrepo.com/show/398374/speaking-head.svg",
        layout="wide",
    )


def import_styles():
    "import styles sheet"
    with open("styles/style.css") as css:
        st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)


def ui_header():
    "UI header"
    # st.title("Open Cloze")
    st.markdown("## Open Cloze")


def sidebar():
    st.sidebar.markdown(
        "# Choose your language",
    )

    # language selector
    st.session_state["selected_language"] = st.sidebar.selectbox(
        "Select language",
        options=st.session_state["language_options"],
        index=8,
    )

    # set selector
    if "language_key" in st.session_state:
        if os.path.exists(
            f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv"
        ):
            st.session_state["set_options"] = list(
                pd.read_csv(
                    f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv"
                )
                .loc[:, "set"]
                .unique()
            )

            st.session_state["selected_set"] = st.sidebar.selectbox(
                "Select set",
                options=st.session_state["set_options"],
                index=0,
            )

    # how many sentences
    st.session_state["num_sentences"] = st.sidebar.number_input(
        "How many sentences in one round",
        min_value=1,
        value=10,
    )

    # use multiple choice?
    st.session_state["use_choice"] = st.sidebar.checkbox("Use multiple choice?")

    # generate pronunciations?
    st.session_state["gen_pronunciation"] = st.sidebar.checkbox(
        "Generate pronunciation?"
    )

    # how many options for multiple choice
    st.session_state["num_choice"] = st.sidebar.number_input(
        "How many options to display for multiple choice",
        min_value=2,
        value=4,
    )

    # percentile difficulty slider
    st.session_state["percentile"] = st.sidebar.slider(
        "Difficulty percentiles",
        min_value=0,
        max_value=100,
        value=(0, 100),
    )

    # run button
    st.session_state["start_round"] = st.sidebar.button(
        "Start the round",
    )


def show_round():
    if "active" not in st.session_state:
        st.session_state["active"] = 0

    if st.session_state["start_round"]:
        # end mid-round
        try:
            del st.session_state["sentence_list"]
            del st.session_state["wrong_counter"]
            del st.session_state["sentence_ids"]
            del st.session_state["sentence_sample"]
            del st.session_state["remaining_sample"]
            del st.session_state["rand_sentence_id"]
            try:
                del st.session_state["options"]
            except:
                pass
        except:
            pass

        st.session_state["persistent_lang_name"] = st.session_state["selected_language"]
        st.session_state["start_time"] = time.time()  # start time of the round

        setup_round()

    if (st.session_state["active"] == 1) and not (st.session_state["start_round"]):
        setup_round()
