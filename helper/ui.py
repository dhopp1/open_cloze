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

    if "metadata" not in st.session_state:
        st.session_state["metadata"] = pd.read_csv("metadata.csv")


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
        index=10,
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

    # randomize
    st.session_state["randomize"] = st.sidebar.checkbox(
        "Randomly sample questions?",
        value=True,
        help="If selected, sentences will be randomly selected for a round. If not, sentences will be sequentialy presented.",
    )

    # how many sentences
    if st.session_state["randomize"]:
        st.session_state["num_sentences"] = st.sidebar.number_input(
            "How many sentences in one round",
            min_value=1,
            value=10,
        )

        # percentile difficulty slider
        st.session_state["percentile"] = st.sidebar.slider(
            "Difficulty percentiles",
            min_value=0,
            max_value=100,
            value=(0, 100),
            help="Which difficulty percentile to sample from. Lower value = easier sentences.",
        )
    else:
        # not random, show sentence numbers
        # info on sentence numbers
        st.session_state["set_info"] = (
            pd.read_csv(
                f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv",
                usecols=["sentence_id", "set"],
                low_memory=True,
            )
            .loc[lambda x: x.set == st.session_state["selected_set"], :]
            .reset_index(drop=True)
        )

        col1, col2 = st.sidebar.columns(2)
        st.session_state["sequential_selection_1"] = col1.number_input(
            "Sentence number start",
            min_value=1,
            max_value=len(st.session_state["set_info"]),
            value=1,
        )
        st.session_state["sequential_selection_2"] = col2.number_input(
            "Sentence number end",
            min_value=1,
            max_value=len(st.session_state["set_info"]),
            value=len(st.session_state["set_info"]),
        )

        st.session_state["sequential_sentence_ids"] = list(
            st.session_state["set_info"]
            .loc[
                lambda x: (x.index >= st.session_state["sequential_selection_1"] - 1)
                & (x.index <= st.session_state["sequential_selection_2"] - 1),
                "sentence_id",
            ]
            .values
        )

    # use multiple choice?
    st.session_state["use_choice"] = st.sidebar.checkbox("Use multiple choice?")

    # how many options for multiple choice
    if st.session_state["use_choice"]:
        st.session_state["num_choice"] = st.sidebar.number_input(
            "How many options to display for multiple choice",
            min_value=2,
            value=4,
        )
    else:
        st.session_state["num_choice"] = 4

    # generate pronunciations?
    st.session_state["gen_pronunciation"] = st.sidebar.checkbox(
        "Generate pronunciation?", help="Add an option to read the sentence aloud"
    )

    # transliteration stuff
    if (
        len(
            pd.read_csv(
                f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv",
                nrows=2,
            ).loc[lambda x: ~pd.isna(x.transliteration), :]
        )
        > 0
    ):
        # show transliteration?
        st.session_state["show_transliteration"] = st.sidebar.checkbox(
            "Show transliteration/original script?",
            help="Shows the transliteration if the language is not written in the latin script. Shows the original script if `Guess transliteration` is checked",
        )

        # guess transliteration?
        st.session_state["guess_transliteration"] = st.sidebar.checkbox(
            "Guess transliteration",
            help="Guess the transliteration rather than the original script",
        )

        # show answer in transliteration?
        st.session_state["show_transliteration_answer"] = st.sidebar.checkbox(
            "Show answer in transliteration?",
            help="Whether or not to show the answer in the transliteration/original script",
        )
    else:
        st.session_state["show_transliteration"] = False
        st.session_state["guess_transliteration"] = False
        st.session_state["show_transliteration_answer"] = False

    # run button
    st.session_state["start_round"] = st.sidebar.button(
        "Start the round",
    )


def show_round():
    if "active" not in st.session_state:
        st.session_state["active"] = 0

    if "restart_round" not in st.session_state:
        st.session_state["restart_round"] = False

    if st.session_state["start_round"] or st.session_state["restart_round"]:
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
