import pandas as pd
import streamlit as st

from helper.data import setup_languages
from helper.questions import setup_round
from helper.stats import calc_stats
from helper.ui import (
    import_styles,
    show_round,
    sidebar,
    ui_header,
    ui_tab,
)
from helper.user_management import check_password, set_user_id


### page setup and authentication
ui_tab()  # icon and page title
ui_header()  # header

if not check_password():
    st.stop()

if "initialized" not in st.session_state:
    st.session_state["initialized"] = 1
    st.info(
        "Select a language and press the `Start the round` button in the sidebar to get started"
    )

set_user_id()

# language options
if "language_options" not in st.session_state:
    st.session_state["language_options"] = list(
        pd.read_csv("metadata.csv").loc[lambda x: x.field == "language", "value"].values
    )


### initialization
import_styles()


### sidebar
sidebar()


### data setup
setup_languages()


### tabs
tabs = st.tabs(["Round", "Stats"])

with tabs[0]:
    ### show the round
    show_round()

with tabs[1]:
    calc_stats()
