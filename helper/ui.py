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
        index=7,
    )

    # how many sentences
    st.session_state["num_sentences"] = st.sidebar.number_input(
        "How many sentences in one round",
        min_value=1,
        value=10,
    )

    # use multiple choice?
    st.session_state["use_choice"] = st.sidebar.checkbox("Use multiple choice?")

    # how many options for multiple choice
    st.session_state["num_choice"] = st.sidebar.number_input(
        "How many options to display for multiple choice",
        min_value=2,
        value=4,
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
