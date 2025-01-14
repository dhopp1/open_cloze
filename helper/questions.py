import datetime
import pandas as pd
import random
import streamlit as st


def setup_round():
    "setup a round with questions"

    st.session_state["active"] = 1

    lang_abr = st.session_state["language_key"][st.session_state["selected_language"]]

    sentence_list = pd.read_csv(
        f"database/{st.session_state['user_id']}/{lang_abr}.csv"
    )

    # random sample
    if "sentence_ids" not in st.session_state:
        st.session_state["sentence_ids"] = [
            random.randint(
                min(sentence_list["sentence_id"]), max(sentence_list["sentence_id"])
            )
            for _ in range(st.session_state["num_sentences"])
        ]

    if "sentence_sample" not in st.session_state:
        st.session_state["sentence_sample"] = sentence_list.iloc[
            st.session_state["sentence_ids"], :
        ]
        st.session_state["sentence_sample"]["done_round"] = 0

    # remaining sample
    if "remaining_sample" not in st.session_state:
        st.session_state["remaining_sample"] = list(
            st.session_state["sentence_sample"]
            .loc[lambda x: x.done_round == 0, "sentence_id"]
            .values
        )

    if len(st.session_state["remaining_sample"]) > 0:
        if "rand_sentence_id" not in st.session_state:
            st.session_state["rand_sentence_id"] = random.choice(
                st.session_state["remaining_sample"]
            )

        st.session_state["english"] = (
            st.session_state["sentence_sample"]
            .loc[
                lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                "english",
            ]
            .values[0]
        )
        st.session_state["translation"] = (
            st.session_state["sentence_sample"]
            .loc[
                lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                "translation",
            ]
            .values[0]
        )

        # english
        st.markdown("### English")
        st.markdown(st.session_state["english"])

        st.markdown("### Translation")
        st.session_state["guess"] = st.text_input("", "")

        columns = st.columns([1, 1, 5])
        with columns[0]:
            st.session_state["check"] = st.button("Check answer")
        with columns[1]:
            st.session_state["next_question"] = st.button("Next question")
        with columns[2]:
            pass

        if st.session_state["check"]:
            if st.session_state["guess"] == st.session_state["translation"]:
                st.info("Correct!")
                st.session_state["sentence_sample"].loc[
                    lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                    "done_round",
                ] = 1
                st.session_state["sentence_sample"].loc[
                    lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                    "n_right",
                ] = (
                    st.session_state["sentence_sample"].loc[
                        lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                        "n_right",
                    ]
                    + 1
                )
            else:
                st.error(f"{st.session_state['translation']}")
                st.session_state["sentence_sample"].loc[
                    lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                    "n_wrong",
                ] = (
                    st.session_state["sentence_sample"].loc[
                        lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                        "n_wrong",
                    ]
                    + 1
                )

            st.session_state["rand_sentence_id"] = random.choice(
                st.session_state["remaining_sample"]
            )

            st.session_state["remaining_sample"] = list(
                st.session_state["sentence_sample"]
                .loc[lambda x: x.done_round == 0, "sentence_id"]
                .values
            )

            if st.session_state["next_question"]:
                st.rerun()
                st.session_state["guess"] = ""

    st.session_state["sentence_sample"].loc[
        :, "last_practiced"
    ] = datetime.date.today().strftime("%Y-%m-%d")

    st.dataframe(
        st.session_state["sentence_sample"].drop(["sentence_id"], axis=1),
        hide_index=True,
        height=5000,
    )
