import os
import pinyin
import pandas as pd
import pykakasi
import stanza
import string
import streamlit as st
import tempfile
import requests
import zipfile
import shutil
import time
from ai4bharat.transliteration import XlitEngine
from arabic_buckwalter_transliteration.transliteration import arabic_to_buckwalter
from sklearn.feature_extraction.text import TfidfVectorizer
from transliterate import translit


# segment chinese and japanese
def segment_language(nlp, sentence):
    doc = nlp(sentence)
    for sentence in doc.sentences:
        seg_result = []
        for word in sentence.words:
            seg_result.append(word.text)

    return seg_result


# transliterate
def do_transliterate(lang, sentence, engine):
    transliteration = ""
    if lang == "Mandarin":
        transliteration = pinyin.get(sentence, format="numerical")
    elif lang == "Russian":
        transliteration = translit(sentence, "ru", reversed=True)
    elif lang == "Greek":
        transliteration = translit(sentence, "el", reversed=True)
    elif lang == "Arabic":
        transliteration = arabic_to_buckwalter(sentence)
    elif lang == "Hindi":
        transliteration = engine.translit_sentence(sentence, lang_code="hi")
    elif lang == "Bengali":
        transliteration = engine.translit_sentence(sentence, lang_code="bn")
    elif lang == "Japanese":
        result = engine.convert(sentence)
        transliteration = "".join([x["hepburn"] for x in result])

    return transliteration


# determining the difficulty of a sentence
def check_dict(dictionary, value, mean_value):
    try:
        return dictionary[value]
    except:
        return mean_value


def calc_tfidf(sentence, tfidf_data_dict, mean_value):
    "get tfidf of an individual string"
    avg = pd.Series(
        [
            check_dict(tfidf_data_dict["weight"], x, mean_value)
            for x in sentence.lower()
            .translate(str.maketrans("", "", string.punctuation + "。" + "、" + "？"))
            .split()
        ]
    ).mean()
    summy = pd.Series(
        [
            check_dict(tfidf_data_dict["weight"], x, mean_value)
            for x in sentence.lower()
            .translate(str.maketrans("", "", string.punctuation + "。" + "、" + "？"))
            .split()
        ]
    ).sum()
    return (avg, summy)


def gen_difficulty(corpus, mean_percentile=0.1):
    # vectorizer
    tfidf = TfidfVectorizer().fit(
        corpus.translation.str.lower().str.translate(
            str.maketrans("", "", string.punctuation + "。" + "、" + "？")
        )
    )
    tfidf_data = pd.DataFrame(
        tfidf.idf_, index=tfidf.get_feature_names_out(), columns=["weight"]
    )
    tfidf_data_dict = tfidf_data.to_dict()

    mean_value = (
        tfidf_data.sort_values(["weight"], ascending=True)[
            : int(len(tfidf_data) * mean_percentile)
        ]
    ).values.mean()  # mean of first 10th percentile for missing values
    scores = [
        pd.Series(calc_tfidf(x, tfidf_data_dict, mean_value)).mean().round(2)
        for x in corpus.translation
    ]  # lower score = easier, higher = harder. mean of sentence sum and mean, to control for hard and long/short sentences

    return scores


def setup_languages():
    if "language_key" not in st.session_state:
        st.session_state["language_key"] = {
            "Arabic": ["ara", "ar"],
            "Bengali": ["ben", "bn"],
            "Czech": ["ces", "cs"],
            "Danish": ["dan", "da"],
            "Dutch": ["nld", "nl"],
            "French": ["fra", "fr"],
            "German": ["deu", "de"],
            "Greek": ["ell", "el"],
            "Hindi": ["hin", "hi"],
            "Hungarian": ["hun", "hu"],
            "Italian": ["ita", "it"],
            "Japanese": ["jpn", "ja"],
            "Mandarin": ["cmn", "zh"],
            "Norwegian": ["nob", "no"],
            "Portuguese": ["por", "pt"],
            "Romanian": ["ron", "ro"],
            "Russian": ["rus", "ru"],
            "Spanish": ["spa", "es"],
            "Swedish": ["swe", "sv"],
            "Turkish": ["tur", "tr"],
        }

    # see if database exists for user
    if not (os.path.exists(f"database/{st.session_state['user_id']}")):
        os.makedirs(f"database/{st.session_state['user_id']}")

    # make round data file for user
    if not (os.path.exists(f"database/{st.session_state['user_id']}/progress.csv")):
        pd.DataFrame(
            columns=[
                "date",
                "language",
                "set",
                "set_progress",
                "n_sentences",
                "n_wrong",
                "seconds",
            ]
        ).to_csv(f"database/{st.session_state['user_id']}/progress.csv", index=False)

    # download language_files
    with st.spinner("Setting up language files..."):
        for language in st.session_state["language_options"]:
            lang_abr = st.session_state["language_key"][language][0]

            # check if CSV file exists
            if not (
                os.path.exists(f"database/{st.session_state['user_id']}/{lang_abr}.csv")
            ):
                # language specific elements
                engine = None
                if lang_abr == "cmn":
                    stanza.download("zh", processors="tokenize")
                elif lang_abr == "jpn":
                    stanza.download("ja", processors="tokenize")
                    engine = pykakasi.kakasi()
                elif lang_abr in ["hin", "ben"]:
                    try:
                        engine = XlitEngine(
                            src_script_type="indic", beam_width=10, rescore=False
                        )
                    except:
                        engine = None

                with tempfile.TemporaryDirectory() as temp_dir:
                    # Download the file
                    url = f"https://www.manythings.org/anki/{lang_abr}-eng.zip"
                    filename = f"{temp_dir}/file.zip"

                    def download_url(url, save_path, chunk_size=128):
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
                        }

                        r = requests.get(url, stream=True, headers=headers)
                        with open(save_path, "wb") as fd:
                            for chunk in r.iter_content(chunk_size=chunk_size):
                                fd.write(chunk)

                    download_url(url, filename)

                    # Unzip the file
                    with zipfile.ZipFile(filename, "r") as zip_ref:
                        zip_ref.extractall(f"{temp_dir}")

                    # read the file to pandas
                    data = pd.read_csv(f"{temp_dir}/{lang_abr}.txt", sep="\t")
                    data = data.iloc[:, :2]
                    data.columns = ["english", "translation"]

                    # add spaces for chinese and japanese
                    if lang_abr == "cmn":
                        nlp = stanza.Pipeline(
                            "zh", processors="tokenize", download_method=None
                        )
                        data["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in data.translation
                        ]
                    elif lang_abr == "jpn":
                        nlp = stanza.Pipeline(
                            "ja", processors="tokenize", download_method=None
                        )
                        data["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in data.translation
                        ]

                    # add columns for last time practiced, number times right, number times wrong
                    data["transliteration"] = [
                        do_transliterate(language, x, engine) for x in data.translation
                    ]
                    data["difficulty"] = gen_difficulty(data, mean_percentile=0.1)
                    data["set"] = "Tatoeba"
                    data["last_practiced"] = ""
                    data["n_right"] = 0
                    data["n_wrong"] = 0
                    data["sentence_id"] = list(range(1, len(data) + 1))
                    data = data.loc[
                        :,
                        ["sentence_id"]
                        + [x for x in data.columns if x != "sentence_id"],
                    ]

                    data.to_csv(
                        f"database/{st.session_state['user_id']}/{lang_abr}.csv",
                        index=False,
                    )

                    # Delete the temporary directory and its contents
                    shutil.rmtree(temp_dir)


def csv_upload():
    with st.sidebar.expander(label="Upload a CSV"):
        st.session_state["uploaded_file"] = st.file_uploader(
            "",
            type=[".csv"],
            help="Upload a CSV with at least two columns, `english` and `translation`",
        )

        st.session_state["csv_set_name"] = st.text_input("Set name of uploaded CSV", "")

        st.session_state["csv_upload_button"] = st.button(
            "Process CSV file",
            help="Click to process the CSV file",
        )

        if st.session_state["csv_upload_button"]:
            with st.spinner("Processing CSV"):
                with open(
                    f"database/{st.session_state['user_id']}/tmp.csv",
                    "wb",
                ) as new_file:
                    new_file.write(
                        st.session_state["uploaded_file"]
                        .getvalue()
                        .decode("latin1")
                        .encode("latin1")
                    )
                    new_file.close()

                tmp = pd.read_csv(f"database/{st.session_state['user_id']}/tmp.csv")

                if "english" in tmp.columns and "translation" in tmp.columns:
                    if st.session_state["selected_language"] in ["Hindi", "Bengali"]:
                        try:
                            engine = XlitEngine(
                                src_script_type="indic", beam_width=10, rescore=False
                            )
                        except:
                            engine = None
                    elif st.session_state["selected_language"] == "Japanese":
                        engine = pykakasi.kakasi()
                    else:
                        engine = None

                    # incorporate the file into the existing database file
                    full = pd.read_csv(
                        f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv"
                    )

                    tmp["transliteration"] = [
                        do_transliterate(
                            st.session_state["selected_language"], x, engine
                        )
                        for x in tmp.translation
                    ]
                    tmp["set"] = st.session_state["csv_set_name"]
                    tmp["last_practiced"] = ""
                    tmp["n_right"] = 0
                    tmp["n_wrong"] = 0
                    tmp["difficulty"] = gen_difficulty(tmp, mean_percentile=0.1)

                    # chinese and japanese tokenization
                    if st.session_state["selected_language"] == "Mandarin":
                        nlp = stanza.Pipeline(
                            "zh", processors="tokenize", download_method=None
                        )
                        tmp["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in tmp.translation
                        ]
                    elif st.session_state["selected_language"] == "Japanese":
                        nlp = stanza.Pipeline(
                            "ja", processors="tokenize", download_method=None
                        )
                        tmp["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in tmp.translation
                        ]

                    max_sentence_id = full.sentence_id.max()
                    tmp["sentence_id"] = list(
                        range(max_sentence_id + 1, max_sentence_id + 1 + len(tmp))
                    )

                    full = pd.concat([full, tmp], ignore_index=True)
                    full.to_csv(
                        f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv",
                        index=False,
                    )

                    st.info("CSV successfully processed!")
                else:
                    st.error(
                        "Please make sure your CSV has an `english` and a `translation` column`"
                    )

                # delete the temporary file
                os.remove(f"database/{st.session_state['user_id']}/tmp.csv")

                time.sleep(5)
                st.rerun()
