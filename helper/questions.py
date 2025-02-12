import datetime
import editdistance
import glob
from gtts import gTTS
import os
import pandas as pd
import random
import re
import streamlit as st
import streamlit.components.v1 as components
import time

from helper.llm import get_gemini


def ordinal(n):
    "convert int to ordinal"
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return str(n) + suffix


def create_cloze_test(
    sentence, reverse=False, n_missing=1
):  # reverse for right to left language like arabic
    words = sentence.split()

    # acceptable words to be missing
    good_range = [
        i
        for i in range(len(words))
        if words[i] not in ["?", ".", ",", "!", "。", "、", "？"]
    ]
    n_missing = min(len(good_range), n_missing)  # can't have more missing than n_words

    # select missing words
    blank_indices = random.sample(good_range, n_missing)
    blank_indices = sorted(blank_indices)
    blank_words = [words[blank_index] for blank_index in blank_indices]
    blank_words = [
        re.sub("[.?¿¡!,。、？]", "", blank_word) for blank_word in blank_words
    ]

    word_list = [
        word if i not in blank_indices else "_____" for i, word in enumerate(words)
    ]

    if reverse:
        word_list = list(reversed(word_list))
    cloze_sentence = " ".join(word_list)
    return cloze_sentence, blank_words, blank_indices, n_missing


def find_closest_words(corpus, target_word, top_n):
    "given a corpus, select top x closest to the target word"

    distances = []
    for word in corpus:
        if word != target_word:
            dist = editdistance.eval(target_word, word)
            distances.append((word, dist))
    distances.sort(key=lambda x: x[1])
    return [x[0] for x in distances[:top_n]]


def gen_multiple_choice(
    sentence_list, target_word, n=3, top_n_sample=100, random_corpus_n=500
):
    "generate 4 options for multiple choice"

    # random sample for corpus
    max_corpus = min(random_corpus_n, len(sentence_list))

    corpus = set(
        re.sub(
            "[.?¿¡!,]",
            "",
            " ".join(
                list(
                    sentence_list.loc[
                        random.sample(list(sentence_list.index), max_corpus),
                        "translation",
                    ].values
                )
            ).lower(),
        ).split()
    )
    sample = find_closest_words(corpus, target_word, top_n_sample)
    return random.sample(sample, n)


def setup_round():
    "setup a round with questions"

    st.session_state["active"] = 1

    lang_abr = st.session_state["language_key"][st.session_state["selected_language"]][
        0
    ]

    if "sentence_list" not in st.session_state:
        st.session_state["full_sentence_list"] = (
            pd.read_csv(f"database/{st.session_state['user_id']}/{lang_abr}.csv")
            .loc[lambda x: x.set == st.session_state["selected_set"], :]
            .reset_index(drop=True)
        )

        # flip transliteration and original if desired
        if st.session_state["guess_transliteration"]:
            transliteration = st.session_state["full_sentence_list"]["transliteration"]
            st.session_state["full_sentence_list"]["transliteration"] = (
                st.session_state["full_sentence_list"]["translation"]
            )
            st.session_state["full_sentence_list"]["translation"] = transliteration

        st.session_state["sentence_list"] = st.session_state[
            "full_sentence_list"
        ]  # because will be edited down later for quantiles

    # percentiles
    if st.session_state["randomize"]:
        lower_bound = st.session_state["sentence_list"].difficulty.quantile(
            st.session_state["percentile"][0] / 100
        )
        upper_bound = st.session_state["sentence_list"].difficulty.quantile(
            st.session_state["percentile"][1] / 100
        )
        st.session_state["sentence_list"] = (
            st.session_state["sentence_list"]
            .loc[
                lambda x: (x.difficulty >= lower_bound) & (x.difficulty <= upper_bound),
                :,
            ]
            .reset_index(drop=True)
        )
    # sequential
    else:
        st.session_state["sentence_list"] = (
            st.session_state["sentence_list"]
            .loc[
                lambda x: x.sentence_id.isin(
                    st.session_state["sequential_sentence_ids"]
                ),
                :,
            ]
            .reset_index(drop=True)
        )

    # wrong counter
    if "wrong_counter" not in st.session_state:
        st.session_state["wrong_counter"] = 0

    # random sample
    if "sentence_ids" not in st.session_state:
        st.session_state["max_num_sentences"] = min(
            st.session_state["num_sentences"], len(st.session_state["sentence_list"])
        )

        if st.session_state["randomize"]:
            st.session_state["sentence_ids"] = random.sample(
                list(st.session_state["sentence_list"]["sentence_id"]),
                st.session_state["max_num_sentences"],
            )
        else:
            st.session_state["sentence_ids"] = st.session_state[
                "sequential_sentence_ids"
            ]

    if "sentence_sample" not in st.session_state:
        with st.spinner("Setting up sample..."):
            st.session_state["sentence_sample"] = (
                st.session_state["sentence_list"]
                .loc[lambda x: x.sentence_id.isin(st.session_state["sentence_ids"]), :]
                .reset_index(drop=True)
            )
            st.session_state["sentence_sample"]["done_round"] = 0

            # create cloze sentences
            st.session_state["sentence_sample"]["difficulty_percentile"] = ""
            st.session_state["sentence_sample"]["cloze_sentence"] = ""
            st.session_state["sentence_sample"]["transliteration_sentence"] = ""
            st.session_state["sentence_sample"]["missing_word"] = ""
            st.session_state["sentence_sample"]["word_index"] = 0
            st.session_state["sentence_sample"]["min_missing"] = 0

            for n_missing in range(st.session_state["n_missing"]):
                st.session_state["sentence_sample"][f"multiple_choice_{n_missing}"] = ""
            if st.session_state["persistent_lang_name"] in ["Arabic"]:
                reverse = True
            else:
                reverse = False
            for i in st.session_state["sentence_sample"].index:
                cloze_sentence, missing_words, word_indices, min_missing = (
                    create_cloze_test(
                        st.session_state["sentence_sample"].loc[i, "translation"],
                        reverse,
                        n_missing=st.session_state["n_missing"],
                    )
                )
                st.session_state["sentence_sample"].loc[
                    i, "cloze_sentence"
                ] = cloze_sentence
                st.session_state["sentence_sample"].loc[i, "min_missing"] = min_missing

                # transliteration
                if st.session_state["show_transliteration"]:
                    transliteration = (
                        st.session_state["sentence_sample"]
                        .loc[i, "transliteration"]
                        .split()
                    )
                    if not (st.session_state["show_transliteration_answer"]):
                        for word_index in word_indices:
                            transliteration[word_index] = "_____"
                    transliteration = " ".join(transliteration)

                    st.session_state["sentence_sample"].loc[
                        i, "transliteration_sentence"
                    ] = transliteration

                for n_missing in range(min_missing):
                    st.session_state["sentence_sample"].loc[
                        i, f"missing_word_{n_missing}"
                    ] = missing_words[n_missing]
                    st.session_state["sentence_sample"].loc[
                        i, f"word_index_{n_missing}"
                    ] = word_indices[n_missing]

                # multiple choice options
                for n_missing in range(min_missing):
                    st.session_state["sentence_sample"].loc[
                        i, f"multiple_choice_{n_missing}"
                    ] = ",".join(
                        gen_multiple_choice(
                            st.session_state["sentence_list"],
                            missing_words[n_missing],
                            n=st.session_state["num_choice"] - 1,
                            top_n_sample=100,
                            random_corpus_n=500,
                        )
                    )

                # difficulty
                st.session_state["sentence_sample"].loc[i, "difficulty_percentile"] = (
                    st.session_state["full_sentence_list"].difficulty
                    < st.session_state["sentence_sample"].loc[i, "difficulty"]
                ).mean()

                # create audio files
                if st.session_state["gen_pronunciation"]:
                    myobj = gTTS(
                        text=st.session_state["sentence_sample"].loc[i, "translation"],
                        lang=st.session_state["language_key"][
                            st.session_state["selected_language"]
                        ][1],
                        slow=False,
                    )
                    myobj.save(
                        f"database/{st.session_state['user_id']}/{st.session_state['sentence_sample'].loc[i, 'sentence_id']}.mp3"
                    )

    # remaining sample
    if "remaining_sample" not in st.session_state:
        st.session_state["remaining_sample"] = list(
            st.session_state["sentence_sample"]
            .loc[lambda x: x.done_round == 0, "sentence_id"]
            .values
        )

    if len(st.session_state["remaining_sample"]) > 0:
        if "rand_sentence_id" not in st.session_state:
            # randomized next choice
            if st.session_state["randomize"]:
                st.session_state["rand_sentence_id"] = random.choice(
                    st.session_state["remaining_sample"]
                )
            # next choice in sequence
            else:
                st.session_state["rand_sentence_id"] = st.session_state["sentence_ids"][
                    0
                ]

        st.session_state["english"] = (
            st.session_state["sentence_sample"]
            .loc[
                lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                "english",
            ]
            .values[0]
        )

        min_missing = (
            st.session_state["sentence_sample"]
            .loc[
                lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                "min_missing",
            ]
            .values[0]
        )

        for n_missing in range(min_missing):
            st.session_state[f"translation_{n_missing}"] = (
                st.session_state["sentence_sample"]
                .loc[
                    lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                    f"missing_word_{n_missing}",
                ]
                .values[0]
            )
        st.session_state["difficulty_percentile"] = (
            st.session_state["sentence_sample"]
            .loc[
                lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                "difficulty_percentile",
            ]
            .values[0]
        )

        # cloze sentence
        st.markdown(
            f'### {st.session_state["sentence_sample"].loc[lambda x: x.sentence_id == st.session_state["rand_sentence_id"], "cloze_sentence"].values[0]}'
        )

        # show transliteration if asked
        if st.session_state["show_transliteration"]:
            st.markdown(
                f'{st.session_state["sentence_sample"].loc[lambda x: x.sentence_id == st.session_state["rand_sentence_id"], "transliteration_sentence"].values[0]}'
            )

        # show english
        st.markdown(st.session_state["english"])

        if "counter" not in st.session_state:
            st.session_state["counter"] = 0
        else:
            st.session_state["counter"] += 1

        # text input or multiple choice
        if not (st.session_state["use_choice"]):
            cols = st.columns(int(min_missing))
            for i, col in enumerate(cols):
                with col:
                    st.session_state[f"guess_{i}"] = st.text_input(
                        "", "", key=f"text_input_{i}"
                    )
        else:
            if "options_0" not in st.session_state:
                for n_missing in range(min_missing):
                    st.session_state[f"options_{n_missing}"] = (
                        st.session_state["sentence_sample"]
                        .loc[
                            lambda x: x.sentence_id
                            == st.session_state["rand_sentence_id"],
                            f"multiple_choice_{n_missing}",
                        ]
                        .values[0]
                    ).split(",") + [st.session_state[f"translation_{n_missing}"]]
                    st.session_state[f"options_{n_missing}"] = random.sample(
                        st.session_state[f"options_{n_missing}"],
                        len(st.session_state[f"options_{n_missing}"]),
                    )
                    st.session_state[f"options_{n_missing}"] = [""] + st.session_state[
                        f"options_{n_missing}"
                    ]

                    # upper case if correct answer is uppercased
                    if st.session_state[f"translation_{n_missing}"][0].isupper():
                        st.session_state[f"options_{n_missing}"] = [
                            x.capitalize()
                            for x in st.session_state[f"options_{n_missing}"]
                        ]

            # columns of multiple choice boxes
            cols = st.columns(int(min_missing))
            for i, col in enumerate(cols):
                with col:
                    st.session_state[f"guess_{i}"] = st.selectbox(
                        "",
                        options=st.session_state[f"options_{i}"],
                        index=0,
                        key=f"multiple_choice_{i}",
                    )

        # show check button if doing more than 1 missing word
        if st.session_state["n_missing"] > 1:
            st.session_state["check_answer"] = st.button("Check answer")
        else:
            st.session_state["check_answer"] = False

        # clear out the text boxes
        def on_click():
            for i in range(min_missing):
                exec(f"""st.session_state.text_input_{i} = "" """)

        st.session_state["next_question"] = st.button(
            "Next question", on_click=on_click
        )
        st.markdown(
            f"{len(st.session_state['remaining_sample'])}/{len(st.session_state['sentence_ids'])} sentences remaining. ({ordinal(round(st.session_state['difficulty_percentile'] * 100, 0))} percentile difficulty)"
        )

        # checking the missing word(s)
        if (st.session_state["check_answer"]) or (
            st.session_state["guess_0"] and st.session_state["n_missing"] == 1
        ):  # first condition is one missing only, check on change, second condition is check button
            if all(
                [
                    st.session_state[f"guess_{i}"]
                    == st.session_state[f"translation_{i}"]
                    for i in range(min_missing)
                ]
            ):
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
                st.session_state[
                    "wrong_counter"
                ] += 1  # how many they got wrong this round
                st.error(
                    ", ".join(
                        [
                            st.session_state[f"translation_{i}"]
                            for i in range(min_missing)
                        ]
                    )
                )
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

        # llm
        if st.session_state["api_key"] != "":
            st.session_state["gen_llm_button"] = st.button(
                "Generate an LLM explanation"
            )
            if st.session_state["gen_llm_button"]:
                with st.spinner("Generating LLM explanation..."):
                    # first questions
                    if "query" not in st.session_state:
                        try:
                            st.session_state["query"] = (
                                st.session_state["sentence_sample"]
                                .loc[
                                    lambda x: x.sentence_id
                                    == st.session_state["rand_sentence_id"],
                                    "translation",
                                ]
                                .values[0]
                            )
                            st.session_state["query"] = (
                                f"Break down the grammer of this {st.session_state['persistent_lang_name']} sentence in a clear and logical way for a language learner to understand, restate the sentence at the top of your answer: {st.session_state['query']}"
                            )

                            st.session_state["response"] = get_gemini(
                                st.session_state["query"],
                                st.session_state["api_key"],
                            )
                        except:
                            st.session_state["response"] = (
                                "Error generating LLM response."
                            )
                        st.session_state["new_query"] = st.text_input(
                            "Follow up question", value=""
                        )
                    else:
                        st.session_state["new_query"] = st.text_input(
                            "Follow up question", value=""
                        )
                        try:
                            st.session_state["query"] = (
                                f"Answer this questiona about {st.session_state['persistent_lang_name']} grammar: {st.session_state['new_query']}. This is the context of the question: {st.session_state['response']}"
                            )

                            st.session_state["response"] = (
                                f'{get_gemini(st.session_state["query"], st.session_state["api_key"])} \n\n **----Prior answer----** \n\n {st.session_state["response"]}'
                            )
                        except:
                            st.session_state["response"] = (
                                "Error generating LLM response."
                            )

                    if st.session_state["response"] == "Error generating LLM response.":
                        st.error(st.session_state["response"])
                    else:
                        st.info(st.session_state["response"])

        # play audio
        if st.session_state["gen_pronunciation"]:
            st.audio(
                f"database/{st.session_state['user_id']}/{st.session_state['rand_sentence_id']}.mp3",
            )

        # mnemonic
        with st.expander("Mnemonic"):
            st.session_state["mnemonic"] = st.text_input(
                "",
                (
                    ""
                    if str(
                        st.session_state["sentence_sample"]
                        .loc[
                            lambda x: x.sentence_id
                            == st.session_state["rand_sentence_id"],
                            "mnemonic",
                        ]
                        .values[0]
                    )
                    == "nan"
                    else str(
                        st.session_state["sentence_sample"]
                        .loc[
                            lambda x: x.sentence_id
                            == st.session_state["rand_sentence_id"],
                            "mnemonic",
                        ]
                        .values[0]
                    )
                ),
                help="Record a mnemonic here to help you remember the phrase/word.",
            )
            st.session_state["mnemonic_button"] = st.button("Record new mnemonic")
            if st.session_state["mnemonic_button"]:
                st.session_state["sentence_sample"].loc[
                    lambda x: x.sentence_id == st.session_state["rand_sentence_id"],
                    "mnemonic",
                ] = st.session_state["mnemonic"]
                st.info("Successfully recorded mnemonic")
                time.sleep(2)
                st.rerun()

        # special characters in this language for copying
        if "special_char_dict" not in st.session_state:
            st.session_state["special_char_dict"] = dict(
                zip(
                    list(
                        st.session_state["metadata"]
                        .loc[lambda x: x.field == "language", "value"]
                        .values
                    ),
                    [
                        x.split(",") if str(x) != "nan" else []
                        for x in st.session_state["metadata"]
                        .loc[lambda x: x.field == "language", "special_chars"]
                        .values.tolist()
                    ],
                )
            )

        special_chars = st.session_state["special_char_dict"][
            st.session_state["persistent_lang_name"]
        ]
        if len(special_chars) > 0:
            st.markdown("**Special characters**")
            upper_chars = [x.upper() for x in special_chars]
            st.code(" ".join(special_chars))
            st.code(" ".join(upper_chars))

        if st.session_state["next_question"]:
            # load a new question
            if st.session_state["randomize"]:
                st.session_state["rand_sentence_id"] = random.choice(
                    st.session_state["remaining_sample"]
                )
            else:
                try:
                    st.session_state["rand_sentence_id"] = st.session_state[
                        "remaining_sample"
                    ][
                        st.session_state["remaining_sample"].index(
                            st.session_state["rand_sentence_id"]
                        )
                        + 1
                    ]
                except:
                    try:
                        st.session_state["rand_sentence_id"] = min(
                            st.session_state["remaining_sample"]
                        )  # go to the beginning of the remaining sample
                    except:
                        pass

            try:
                del st.session_state["options_0"]
            except:
                pass

            try:
                del st.session_state["query"]
                del st.session_state["response"]
            except:
                pass

            st.session_state["remaining_sample"] = list(
                st.session_state["sentence_sample"]
                .loc[lambda x: x.done_round == 0, "sentence_id"]
                .values
            )

            st.rerun()

        # to empty and autohighlight guess box
        if not (st.session_state["use_choice"]) and st.session_state["n_missing"] == 1:
            components.html(
                f"""
                    <div></div>
                    <p style="display: none;">{st.session_state.counter}</p>
                    <script>
                        var input = window.parent.document.querySelectorAll("input[type=text]");
                        for (var i = 0; i < (input.length - {min_missing + 1}); ++i) {{
                            input[i].focus();
                        }}
                </script>
                """,
                height=150,
            )

    # finished the round
    else:
        # showing finish info
        st.session_state["sentence_list"] = pd.read_csv(
            f"database/{st.session_state['user_id']}/{lang_abr}.csv"
        )
        total = len(
            st.session_state["sentence_list"].loc[
                lambda x: x.set == st.session_state["selected_set"], :
            ]
        )
        n_done = min(
            total,
            len(
                st.session_state["sentence_list"].loc[
                    lambda x: (x.n_right >= 1)
                    & (x.set == st.session_state["selected_set"]),
                    :,
                ]
            )
            + len(st.session_state["sentence_sample"]),
        )  # include those you just did

        st.session_state["end_time"] = time.time()

        with st.spinner("Recording progress..."):
            # saving progress to disk
            # recording the date
            st.session_state["sentence_sample"].loc[
                :, "last_practiced"
            ] = datetime.date.today().strftime("%Y-%m-%d")
            merged_df = pd.merge(
                st.session_state["sentence_list"],
                st.session_state["sentence_sample"].loc[
                    :,
                    ["mnemonic", "sentence_id", "n_right", "n_wrong", "last_practiced"],
                ],
                how="left",
                on="sentence_id",
                suffixes=("_A", "_B"),
            )

            # overwrite values in A with values from B where key is present in B
            merged_df["mnemonic"] = merged_df.apply(
                lambda row: (
                    row["mnemonic_B"]
                    if not pd.isna(row["mnemonic_B"])
                    else row["mnemonic_A"]
                ),
                axis=1,
            )

            merged_df["n_right"] = merged_df.apply(
                lambda row: (
                    row["n_right_B"]
                    if not pd.isna(row["n_right_B"])
                    else row["n_right_A"]
                ),
                axis=1,
            )
            merged_df["n_wrong"] = merged_df.apply(
                lambda row: (
                    row["n_wrong_B"]
                    if not pd.isna(row["n_wrong_B"])
                    else row["n_wrong_A"]
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
                    "mnemonic_A",
                    "mnemonic_B",
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

            # progress file
            progress = pd.read_csv(
                f"database/{st.session_state['user_id']}/progress.csv"
            )
            tmp_df = pd.DataFrame(
                {
                    "date": [datetime.date.today().strftime("%Y-%m-%d")],
                    "language": [st.session_state["persistent_lang_name"]],
                    "set": [st.session_state["selected_set"]],
                    "set_progress": [round((n_done / total), 6)],
                    "n_sentences": [st.session_state["num_sentences"]],
                    "n_wrong": [st.session_state["wrong_counter"]],
                    "seconds": [
                        st.session_state["end_time"] - st.session_state["start_time"]
                    ],
                }
            )
            pd.concat([progress, tmp_df], ignore_index=True).to_csv(
                f"database/{st.session_state['user_id']}/progress.csv",
                index=False,
                float_format="%.6f",
            )

            # deleting audio files
            mp3_files = glob.glob(
                os.path.join(f"database/{st.session_state['user_id']}/", "*.mp3")
            )
            if len(mp3_files) > 0:
                for file in mp3_files:
                    os.remove(file)

            # success message
            st.info(
                f"Successfully studied {len(st.session_state['sentence_ids'])} sentences in {round((st.session_state['end_time'] - st.session_state['start_time'])/60, 0):.0f} minute(s). You have studied {(n_done/total * 100):.6f}% of sentences."
            )

            # deleting session state variables
            try:
                del st.session_state["sentence_list"]
                del st.session_state["wrong_counter"]
                del st.session_state["sentence_ids"]
                del st.session_state["sentence_sample"]
                del st.session_state["remaining_sample"]
                del st.session_state["rand_sentence_id"]
                del st.session_state["start_time"]
            except:
                pass

            st.session_state["restart_round"] = st.button("Replay")
            st.session_state["start_time"] = time.time()
