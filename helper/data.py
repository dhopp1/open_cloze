import os
import pandas as pd
import streamlit as st
import tempfile
import requests
import zipfile
import shutil


def setup_languages():
    if "language_key" not in st.session_state:
        st.session_state["language_key"] = {
            "Bengali": "ben",
            "Czech": "ces",
            "Danish": "dan",
            "Dutch": "nld",
            "French": "fra",
            "German": "deu",
            "Greek": "ell",
            "Hindi": "hin",
            "Hungarian": "hun",
            "Italian": "ita",
            "Japanese": "jpn",
            "Mandarin": "cmn",
            "Norwegian": "nob",
            "Portuguese": "por",
            "Romanian": "ron",
            "Russian": "rus",
            "Spanish": "spa",
            "Swedish": "swe",
            "Turkish": "tur",
        }

    # see if database exists for user
    if not (os.path.exists(f"database/{st.session_state['user_id']}")):
        os.makedirs(f"database/{st.session_state['user_id']}")

    # make round data file for user
    if not (os.path.exists(f"database/{st.session_state['user_id']}/progress.csv")):
        pd.DataFrame(
            columns=["date", "language", "n_sentences", "n_wrong", "seconds"]
        ).to_csv(f"database/{st.session_state['user_id']}/progress.csv", index=False)

    # download language_files
    with st.spinner("Setting up language files..."):
        for language in st.session_state["language_options"]:
            lang_abr = st.session_state["language_key"][language]

            # check if CSV file exists
            if not (
                os.path.exists(f"database/{st.session_state['user_id']}/{lang_abr}.csv")
            ):
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

                    # add columns for last time practiced, number times right, number times wrong
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
