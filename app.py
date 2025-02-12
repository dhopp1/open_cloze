import pandas as pd
import streamlit as st

from helper.data import csv_upload, setup_languages
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

### data setup
setup_languages()

### sidebar
sidebar()
csv_upload()

### tabs
tabs = st.tabs(["Round", "Stats", "README"])

with tabs[0]:
    ### show the round
    show_round()

with tabs[1]:
    calc_stats()

with tabs[2]:
    st.markdown(
        """### Overview
The application gives presents you with a sentence in your learning language with a word missing and the English translation. You try to fill in the missing word. The initial sentence list comes from [https://www.manythings.org/anki/](https://www.manythings.org/anki/), but you can add your own sentences. If you add one-word sentence pairs, it's analogous to a flashcard app.

### Select set
You can have more than one sentence set per language, which you can select via the `Select set` dropdown. The default one loaded from manythings.org is the `Tatoeba` set, which includes a large sample of sentences per language. If you add more of your own later, they will appear in the dropdown.

### Types of rounds
In the sidebar, check `Randomly sampled questions?` to practice a certain amount of randomly selected sentences in a round. You can decide how many to practice in a single round via the `How many sentences in one round` field.

The `Difficulty percentiles` slider lets you choose if you want to practice easier or harder sentences. The lower the percentile, the easier the sentences.

If you uncheck `Randomly sampled questions?`, the sentences will be presented to you in order. You can use `Sentence number start` and `Sentence number start` end to dictate which sentences you want to practice. This is useful if for instance you input an article you want to practice and read and want the sentences provided in order.

### Round options
- `Use multiple choice?`: whether to use multiple choice or direct text input. If you choose multiple choice, you can choose how many options to be given.
- `How many missing words in the cloze sentence`: how many blank spaces you want to have to guess in the sentence.
- `Generate pronuncation?`: whether or not to produce audio of the sentences being read aloud.
- `Show transliteration/original script?`: if the language isn't written in the latin script, whether or not to also show the transliteration. Automatic transliteration is currently available for Arabic, Russian, Greek, Hindi, Bengali, Japanese, and Mandarin.
- `Guess transliteration?`: you can guess the transliteration rather than the original script if that is easier for you.
- `Show answer in transliteration?`: if showing transliteration, whether or not to show the answer in the transliteration.

### Mnemonics
During a round, click the `Mnemonic` dropdown to view and record mnemonics for a sentence/term to help you remember it. These will be saved and displayed across rounds.

### Stats
The `Stats` tab shows you various statistics of your usage. It shows you a progress bar of how many of the sentences in the selected set you have already studied.

Change the date range to view statistics for different periods of time. Change the time aggregation to get your stats by day, week, month, or year.

- `Number of sentences studied`: this plot shows the number of sentences/terms studied over a given period of time
- `Minutes spent studying`: this plot shows the number of minutes spent studying over a given period of time
- `Set progress over time`: this plot shows the percentage of the set completed over time
- `Wrong/right ratio`: this plot shows the ratio between the number of wrong answer to right answers over a given period of time. E.g., a ratio of 0 means that you got every answer right on your first try, a ratio of 2 means that you made two mistakes for every correct answer you entered.

### Uploading your own data
In addition to the sentence lists from manythings.org, you can upload your own. You have three options for uploading via the `Upload data` dropdown in the sidebar:

1. upload a CSV with an `english` and a `translation` column
2. upload a .txt file with raw text of the learning langauge. This file will automatically be split into sentences and translated with Google Translate.
3. Similar to 2., you can paste the text you want to convert to a study set directly into the `Paste text directly` box

When uploading your own data, put the name you want the set to have in the `Set name of uploaded data` text field.

You can delete unwanted sets from a language by putting the set's name in the `Set name of uploaded data` field and pressing the `Delete set from database` button.
"""
    )
