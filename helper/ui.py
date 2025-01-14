import streamlit as st

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
    pass
    # st.title("")


def sidebar():
    st.sidebar.markdown(
        "# Open Cloze",
    )

    st.sidebar.markdown(
        "# Choose your language",
    )

    # language selector
    st.session_state["selected_language"] = st.sidebar.selectbox(
        "Select language",
        options=st.session_state["language_options"],
        index=0,
    )

    # how many sentences
    st.session_state["num_sentences"] = st.sidebar.number_input(
        "How many sentences in one round",
        min_value=1,
        value=10,
    )

    # run button
    st.session_state["start_round"] = st.sidebar.button(
        "Start the round",
    )


def show_round():
    if "active" not in st.session_state:
        st.session_state["active"] = 0

    if st.session_state["start_round"] or st.session_state["active"] == 1:
        setup_round()
