import datetime
import pandas as pd
import random
import re
import streamlit as st
import streamlit.components.v1 as components


def create_cloze_test(sentence):
    words = sentence.split()
    if len(words) < 2:
        return (
            None,
            None,
            None,
        )  # Ensure there are at least two words to avoid trivial tests
    blank_index = random.randint(0, len(words) - 1)
    blank_word = re.sub("[.?¿¡!,]", "", words[blank_index])
    cloze_sentence = " ".join(
        [word if i != blank_index else "_____" for i, word in enumerate(words)]
    )
    return cloze_sentence, blank_word, blank_index


def setup_round():
    "setup a round with questions"

    st.markdown(f"## Open Cloze - {st.session_state['selected_language']}")

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

        # create cloze sentences
        st.session_state["sentence_sample"]["cloze_sentence"] = ""
        st.session_state["sentence_sample"]["missing_word"] = ""
        st.session_state["sentence_sample"]["word_index"] = 0
        for i in st.session_state["sentence_sample"].index:
            cloze_sentence, missing_word, word_index = create_cloze_test(
                st.session_state["sentence_sample"].loc[i, "translation"]
            )
            st.session_state["sentence_sample"].loc[
                i, "cloze_sentence"
            ] = cloze_sentence
            st.session_state["sentence_sample"].loc[i, "missing_word"] = missing_word
            st.session_state["sentence_sample"].loc[i, "word_index"] = word_index

    # remaining sample
    if "remaining_sample" not in st.session_state:
        st.session_state["remaining_sample"] = list(
            st.session_state["sentence_sample"]
            .loc[lambda x: x.done_round == 0, "sentence_id"]
            .values
        )

    st.markdown(
        f"{len(st.session_state['remaining_sample'])}/{st.session_state['num_sentences']} sentences remaining."
    )
    st.divider()

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
                "missing_word",
            ]
            .values[0]
        )

        # english
        st.markdown(
            f'### {st.session_state["sentence_sample"].loc[lambda x: x.sentence_id == st.session_state["rand_sentence_id"], "cloze_sentence"].values[0]}'
        )
        if "counter" not in st.session_state:
            st.session_state["counter"] = 0
        else:
            st.session_state["counter"] += 1

        st.session_state["guess"] = st.text_input(st.session_state["english"], "")

        st.session_state["next_question"] = st.button("Next question")

        # checking the missing word
        if st.session_state["guess"]:
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

        if st.session_state["next_question"]:
            # load a new question
            st.session_state["rand_sentence_id"] = random.choice(
                st.session_state["remaining_sample"]
            )

            st.session_state["remaining_sample"] = list(
                st.session_state["sentence_sample"]
                .loc[lambda x: x.done_round == 0, "sentence_id"]
                .values
            )

            st.rerun()

        # to empty and autohighlight guess box
        components.html(
            f"""
                <div></div>
                <p style="display: none;">{st.session_state.counter}</p>
                <script>
                    var input = window.parent.document.querySelectorAll("input[type=text]");
        
                    for (var i = 0; i < input.length; ++i) {{
                        input[i].focus();
                    }}
            </script>
            """,
            height=150,
        )

    # finished the round
    else:
        # showing finish info
        sentence_list = pd.read_csv(
            f"database/{st.session_state['user_id']}/{lang_abr}.csv"
        )
        n_done = len(sentence_list.loc[lambda x: x.n_right >= 1, :])
        total = len(sentence_list)

        st.info(
            f"Successfully studied {st.session_state['num_sentences']} sentences. You have studied {(n_done/total * 100):.6f}% of sentences."
        )

        # saving progress to disk
        # recording the date
        st.session_state["sentence_sample"].loc[
            :, "last_practiced"
        ] = datetime.date.today().strftime("%Y-%m-%d")
        merged_df = pd.merge(
            sentence_list,
            st.session_state["sentence_sample"].loc[
                :, ["sentence_id", "n_right", "n_wrong", "last_practiced"]
            ],
            how="left",
            on="sentence_id",
            suffixes=("_A", "_B"),
        )

        # overwrite values in A with values from B where key is present in B
        merged_df["n_right"] = merged_df.apply(
            lambda row: (
                row["n_right_B"] if not pd.isna(row["n_right_B"]) else row["n_right_A"]
            ),
            axis=1,
        )
        merged_df["n_wrong"] = merged_df.apply(
            lambda row: (
                row["n_wrong_B"] if not pd.isna(row["n_wrong_B"]) else row["n_wrong_A"]
            ),
            axis=1,
        )
        merged_df["last_practiced"] = merged_df.apply(
            lambda row: (
                row["last_practiced_B"]
                if not pd.isna(row["last_practiced_B"])
                else row["last_practiced_A"]
            ),
            axis=1,
        )
        merged_df = merged_df.drop(
            [
                "n_right_A",
                "n_right_B",
                "n_wrong_A",
                "n_wrong_B",
                "last_practiced_A",
                "last_practiced_B",
            ],
            axis=1,
        )
        merged_df.to_csv(
            f"database/{st.session_state['user_id']}/{lang_abr}.csv", index=False
        )

        # deleting session state variables
        del st.session_state["sentence_ids"]
        del st.session_state["sentence_sample"]
        del st.session_state["remaining_sample"]
        del st.session_state["rand_sentence_id"]
