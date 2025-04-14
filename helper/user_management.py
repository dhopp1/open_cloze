import hmac
from datetime import datetime, timedelta
import extra_streamlit_components as stx

import pandas as pd
import streamlit as st


def get_cookie_manager():
    return stx.CookieManager()


def check_password():
    """Check if a user entered the password correctly"""
    st.session_state["cookie_manager"] = get_cookie_manager()

    if st.session_state["cookie_manager"].get(cookie="logged_in") == True:
        st.session_state["user_name"] = st.session_state["cookie_manager"].get(
            cookie="username"
        )
        st.session_state["password_correct"] = True

    # user list
    if "users_list" not in st.session_state:
        st.session_state["users_list"] = list(
            st.session_state["metadata"]
            .loc[lambda x: x.field == "username", "value"]
            .values
        )

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            condition = hmac.compare_digest(
                st.session_state["password"],
                st.secrets["password"],
            )
        except:
            condition = False

        if condition:
            # cookie
            expires_at = datetime.now() + timedelta(days=30)
            st.session_state["cookie_manager"].set(
                cookie="logged_in", val="true", expires_at=expires_at, key="logged_in"
            )
            st.session_state["cookie_manager"].set(
                cookie="username",
                val=st.session_state["user_name"],
                expires_at=expires_at,
                key="user_cookie",
            )

            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # show input for user name
    st.session_state["user_name"] = st.selectbox(
        "User",
        st.session_state["users_list"],
        index=None,
        placeholder="Select user...",
    )

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("Password incorrect")

    return False


def set_user_id():
    "get a user's id from their name"
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = (
            st.session_state["user_name"].lower().replace(" ", "_")
        )
