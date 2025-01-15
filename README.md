# open_cloze
This application provides a front end for practicing cloze tests. It supports any language listed on [https://www.manythings.org/anki/](https://www.manythings.org/anki/). You can try it for free at [https://open-cloze.streamlit.app/](https://open-cloze.streamlit.app/) with user `User` and password `password`, though individual progress won't be saved unless you self-host.

## Installation
- Install the libraries in `requirements.txt`
- Clone this repo
- Edit `.streamlit/secrets.toml` to set the password for your page
- Edit the `metadata.csv` file to add additional users and languages to your application.
- To add languages beyond those already in the metadata file, find the desired language at [https://www.manythings.org/anki/](https://www.manythings.org/anki/), add the language to the `metadata.csv` file, and add a new dictionary entry in the `helper/data.py` file mapping the language's name to its abbreviation on manythings.org.
- Run the application by navigating to the directory where you cloned the repository and running `streamlit run app.py`. This should open a browser window to the application. Progress is saved on a user-level in the `database/` directory.

## Sample image
![Example image](example_screen.png)