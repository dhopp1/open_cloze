try:
    import opencc

    simplify_chinese = True
except:
    simplify_chinese = False
import os
import pinyin
import pandas as pd
import pykakasi
import stanza
import string
import streamlit as st
import tempfile
import re
import requests
import zipfile
import shutil
import time
from ai4bharat.transliteration import XlitEngine
from arabic_buckwalter_transliteration.transliteration import arabic_to_buckwalter
from aksharamukha import transliterate
from mtranslate import translate
from sklearn.feature_extraction.text import TfidfVectorizer
from transliterate import translit


def google_trans(stringx, source_lang):
    "google translate a text and put it in sentence pair format"
    punc_list = [".", "!", "?", "。", "？", "！"]
    sentences = re.split(rf'([{"".join(punc_list)}])', stringx)

    # adding back punctuation
    for i in range(1, len(sentences)):
        if sentences[i] in punc_list:
            sentences[i - 1] = sentences[i - 1] + sentences[i]

    sentences = [x for x in sentences if x not in punc_list + [""]]
    translated_sentences = [""] * len(sentences)

    for i in range(len(sentences)):
        translated_sentences[i] = translate(sentences[i], "en", source_lang)

    data = pd.DataFrame(
        {
            "english": translated_sentences,
            "translation": sentences,
        }
    )

    data = data.loc[lambda x: (x.english != "") & (x.translation != ""), :]

    return data


# segment chinese and japanese
def segment_language(nlp, sentence):
    doc = nlp(sentence)
    for sentence in doc.sentences:
        seg_result = []
        for word in sentence.words:
            seg_result.append(word.text)

    return seg_result


# korean transliteration
def ko_transliterate(text):
    # Mapping tables for Revised Romanization
    INITIALS = [
        "g",
        "kk",
        "n",
        "d",
        "tt",
        "r",
        "m",
        "b",
        "pp",
        "s",
        "ss",
        "",
        "j",
        "jj",
        "ch",
        "k",
        "t",
        "p",
        "h",
    ]

    MEDIALS = [
        "a",
        "ae",
        "ya",
        "yae",
        "eo",
        "e",
        "yeo",
        "ye",
        "o",
        "wa",
        "wae",
        "oe",
        "yo",
        "u",
        "wo",
        "we",
        "wi",
        "yu",
        "eu",
        "ui",
        "i",
    ]

    FINALS = [
        "",
        "k",
        "k",
        "ks",
        "n",
        "nj",
        "nh",
        "t",
        "l",
        "lk",
        "lm",
        "lb",
        "ls",
        "lt",
        "lp",
        "lh",
        "m",
        "p",
        "ps",
        "t",
        "t",
        "ng",
        "t",
        "t",
        "k",
        "t",
        "p",
        "h",
    ]

    # Hangul Unicode base values
    HANGUL_BASE = 0xAC00
    CHOSUNG_BASE = 588
    JOONGSUNG_BASE = 28

    def decompose_hangul(char):
        code = ord(char)
        if not (0xAC00 <= code <= 0xD7A3):
            return char  # Not a Hangul syllable

        syllable_index = code - HANGUL_BASE
        cho = syllable_index // CHOSUNG_BASE
        jung = (syllable_index % CHOSUNG_BASE) // JOONGSUNG_BASE
        jong = syllable_index % JOONGSUNG_BASE

        return INITIALS[cho] + MEDIALS[jung] + FINALS[jong]

    def transliterate_korean_to_latin(text):
        result = ""
        for char in text:
            result += decompose_hangul(char)
        return result

    return transliterate_korean_to_latin(text)


# transliterate
def do_transliterate(lang, sentence, engine=None):
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
        try:
            transliteration = engine.translit_sentence(sentence, lang_code="hi")
        except:
            transliteration = ""
    elif lang == "Bengali":
        try:
            transliteration = engine.translit_sentence(sentence, lang_code="bn")
        except:
            transliteration = ""
    elif lang == "Japanese":
        result = engine.convert(sentence)
        transliteration = "".join([x["hepburn"] for x in result])
    elif lang == "Farsi":
        transliteration = transliterate.process(
            "Arab-Fa", "Latn", sentence, nativize=True
        )
    elif lang == "Korean":
        transliteration = ko_transliterate(sentence)

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
        st.session_state["language_key"] = dict(
            zip(
                list(
                    st.session_state["metadata"]
                    .loc[lambda x: x.field == "language", "value"]
                    .values
                ),
                st.session_state["metadata"]
                .loc[lambda x: x.field == "language", ["manythings_abbr", "gt_abbr"]]
                .values.tolist(),
            )
        )

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
        # first try taking template db
        if True:
            if (
                len(
                    [
                        x
                        for x in os.listdir(f"database/{st.session_state['user_id']}/")
                        if ".csv" in x
                    ]
                )
                == 1
            ):  # check if this has already been done
                # unzip the file
                with zipfile.ZipFile("db_template.zip", "r") as zip_ref:
                    zip_ref.extractall(".")

                # copy to database folder
                for file in os.listdir("db_template/"):
                    shutil.copyfile(
                        f"db_template/{file}",
                        f"database/{st.session_state['user_id']}/{file}",
                    )

                # remove the unzipped directory
                shutil.rmtree("db_template/")

        # if fail, rebuild the db from scratch
        else:
            pass

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
                        # tokenization
                        nlp = stanza.Pipeline(
                            "zh", processors="tokenize", download_method=None
                        )
                        data["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in data.translation
                        ]

                        # converting to simplified characters
                        if simplify_chinese:
                            converter = opencc.OpenCC("t2s.json")
                            data["translation"] = [
                                converter.convert(x) for x in data.translation
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
                    data["missing_indices"] = ""
                    data["difficulty"] = gen_difficulty(data, mean_percentile=0.1)
                    data["set"] = "Tatoeba"
                    data["last_practiced"] = ""
                    data["n_right"] = 0
                    data["n_wrong"] = 0
                    data["sentence_id"] = list(range(1, len(data) + 1))
                    data["mnemonic"] = ""
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
    with st.sidebar.expander(label="Upload data"):
        st.session_state["uploaded_file"] = st.file_uploader(
            "",
            type=[".csv", ".txt"],
            help="Upload a CSV with at least two columns, `english` and `translation`, or a .txt file in your learning language. If a .txt file is uploaded, it will be translated with Google translate and the sentence pairs will automatically be created. You can include an additional column called `missing_indices` with a comma separated list of numbers specifying which word should be the cloze word. E.g., if the translation is `mi nombre es Tom`, you can put `1,3,4` in the  `missing_indices` column. Which means if one missing word is selected `mi` will be the missing word, if two is selected, `mi` and `es` will be the missing words, etc.",
        )

        # direct text input
        st.session_state["direct_text"] = st.text_input(
            "Paste text directly",
            "",
            help="Paste text to add directly here rather than upload a file.",
        )

        st.session_state["csv_set_name"] = st.text_input(
            "Set name of uploaded data", ""
        )

        st.session_state["csv_upload_button"] = st.button(
            "Process data file",
            help="Click to process the data file",
        )

        if st.session_state["csv_upload_button"]:
            with st.spinner("Processing data..."):
                # file upload
                try:
                    extension = (
                        st.session_state["uploaded_file"].name.split(".")[-1].lower()
                    )

                    with open(
                        f"database/{st.session_state['user_id']}/tmp.{extension}",
                        "wb",
                    ) as new_file:
                        new_file.write(
                            st.session_state["uploaded_file"]
                            .getvalue()
                            .decode("latin1")
                            .encode("latin1")
                        )
                        new_file.close()

                    if extension == "csv":
                        tmp = pd.read_csv(
                            f"database/{st.session_state['user_id']}/tmp.csv"
                        )
                    else:
                        # function for google translate .txt to autogenerate sentences
                        with open(
                            f"database/{st.session_state['user_id']}/tmp.{extension}",
                            "r",
                        ) as file:
                            stringx = file.read()
                        tmp = google_trans(
                            stringx,
                            st.session_state["language_key"][
                                st.session_state["selected_language"]
                            ][1],
                        )
                    # direct text pasting
                except:
                    tmp = google_trans(
                        st.session_state["direct_text"],
                        st.session_state["language_key"][
                            st.session_state["selected_language"]
                        ][1],
                    )

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

                    tmp["set"] = st.session_state["csv_set_name"]
                    tmp["last_practiced"] = ""
                    tmp["n_right"] = 0
                    tmp["n_wrong"] = 0
                    if "missing_indices" not in tmp.columns:
                        tmp["missing_indices"] = ""
                    tmp["difficulty"] = gen_difficulty(tmp, mean_percentile=0.1)
                    tmp["mnemonic"] = ""

                    # chinese and japanese tokenization
                    if st.session_state["selected_language"] == "Mandarin":
                        # tokenize
                        nlp = stanza.Pipeline(
                            "zh", processors="tokenize", download_method=None
                        )
                        tmp["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in tmp.translation
                        ]

                        # convert to simplified characters
                        if simplify_chinese:
                            converter = opencc.OpenCC("t2s.json")
                            tmp["translation"] = [
                                converter.convert(x) for x in tmp.translation
                            ]
                    elif st.session_state["selected_language"] == "Japanese":
                        nlp = stanza.Pipeline(
                            "ja", processors="tokenize", download_method=None
                        )
                        tmp["translation"] = [
                            " ".join(segment_language(nlp, x)) for x in tmp.translation
                        ]

                    tmp["transliteration"] = [
                        do_transliterate(
                            st.session_state["selected_language"], x, engine
                        )
                        for x in tmp.translation
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

                    st.info("Data successfully processed!")
                else:
                    st.error(
                        "Please make sure your CSV has an `english` and a `translation` column`"
                    )

                # delete the temporary file
                try:
                    os.remove(f"database/{st.session_state['user_id']}/tmp.{extension}")
                except:
                    pass

                time.sleep(5)
                st.rerun()

        # clear out a set
        st.session_state["csv_clear_button"] = st.button(
            "Delete set from database",
            help="Click to remove a set from your database to clean it up. It will remove the set with the name in the field `Set name of uploaded data`.",
        )

        if st.session_state["csv_clear_button"]:
            data = pd.read_csv(
                f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv"
            )
            data = data.loc[
                lambda x: (x.set != st.session_state["csv_set_name"])
                & (x.set != "")
                & (~pd.isna(x.set)),
                :,
            ].reset_index(drop=True)
            data.to_csv(
                f"database/{st.session_state['user_id']}/{st.session_state['language_key'][st.session_state['selected_language']][0]}.csv",
                index=False,
            )
            st.info("Set successfully removed!")
            time.sleep(2)
            st.rerun()
