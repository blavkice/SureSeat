"""SureSeat - Streamlit UI.

This module is intentionally thin: it wires the Streamlit interface to the
domain logic in the :mod:`sureseat` package and orchestrates the three user
flows (launch booking, validate-only, clean inbox).
"""

import random
import signal
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from sureseat import chrome
from sureseat.config import API_BATCH_SIZE, MAX_WORKERS, ORARI, ORARI_DISPLAY
from sureseat.booking import BookingClient, EmailClient, Validator
from sureseat.booking.api import build_session
from sureseat.crypto import CredentialStore
from sureseat.storage import PlacesStore

places_store = PlacesStore()
credential_store = CredentialStore()


# Cached resources

@st.cache_resource(show_spinner=False)
def get_driver_path():
    """ChromeDriver path, resolved once per session."""
    return chrome.resolve_driver_path()


def get_http_session():
    if "http_session" not in st.session_state:
        st.session_state.http_session = build_session()
    return st.session_state.http_session


def get_email_client():
    """A single EmailClient bound to the current credentials."""
    user = st.session_state.email_user
    password = st.session_state.email_pass
    client = st.session_state.get("email_client")
    if client is None or client.user != user or client.app_password != password:
        if client is not None:
            client.close()
        client = EmailClient(user, password)
        st.session_state.email_client = client
    return client


# Time-slot callbacks

def on_start_change(idx):
    new_start = st.session_state[f"start_{idx}"]
    start_idx = ORARI.index(new_start)
    new_end = ORARI[(start_idx + 8) % len(ORARI)]
    st.session_state.time_slots[idx]["start"] = new_start
    st.session_state.time_slots[idx]["end"] = new_end
    st.session_state[f"end_{idx}"] = new_end


def _validate_links(tasks, driver_path):
    """Run a batch of {'index', 'link'} validations in parallel."""
    validator = Validator(driver_path)
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(validator.validate, t["link"], t["index"]): t
            for t in tasks
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results


# Page setup

st.set_page_config(page_title="SureSeat", layout="wide")
st.title("SureSeat")

if "history" not in st.session_state:
    st.session_state.history = []
if "time_slots" not in st.session_state:
    st.session_state.time_slots = [{"start": "14:00", "end": "18:00"}]
if "places" not in st.session_state:
    st.session_state.places = places_store.load()
if "email_user" not in st.session_state:
    st.session_state.email_user = ""
if "email_pass" not in st.session_state:
    st.session_state.email_pass = ""

if not st.session_state.email_user or not st.session_state.email_pass:
    loaded_email, loaded_pass = credential_store.load()
    if loaded_email and loaded_pass:
        st.session_state.email_user = loaded_email
        st.session_state.email_pass = loaded_pass


# Sidebar

with st.sidebar:
    st.header("Configuration")

    with st.expander("Email Settings", expanded=not st.session_state.email_user):
        email_user = st.text_input("Gmail Address", value=st.session_state.email_user,
                                    key="email_input")
        email_pass = st.text_input("App Password", value=st.session_state.email_pass,
                                   type="password", key="pass_input",
                                   help="Generate at: https://myaccount.google.com/apppasswords")

        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button("Save", use_container_width=True):
                if email_user and email_pass:
                    st.session_state.email_user = email_user
                    st.session_state.email_pass = email_pass
                    if credential_store.save(email_user, email_pass):
                        st.success("Saved (encrypted)")
                    else:
                        st.warning("Saved to session but failed to save credentials")
                else:
                    st.error("Please fill both fields")
        with col_clear:
            if st.button("Clear", use_container_width=True):
                st.session_state.email_user = ""
                st.session_state.email_pass = ""
                st.rerun()

    st.subheader("Places")

    with st.expander("Add New Place", expanded=len(st.session_state.places) == 0):
        st.markdown("""
        Find Resource ID:
        1. Go to affluences.com
        2. Book any seat
        3. Copy ID from URL: affluences.com/reservation/12345
        """)
        place_name = st.text_input("Place Name",
                                    placeholder="e.g., Sala Inglese - Posto 217",
                                    key="new_place_name")
        place_id = st.text_input("Resource ID", placeholder="e.g., 20530",
                                 key="new_place_id")
        if st.button("Add Place", use_container_width=True):
            if place_name and place_id:
                st.session_state.places.append({"name": place_name, "id": place_id})
                if places_store.save(st.session_state.places):
                    st.success(f"Added & Saved: {place_name}")
                else:
                    st.warning(f"Added (but failed to save to file): {place_name}")
                st.rerun()
            else:
                st.error("Please fill both fields")

    if st.session_state.places:
        for idx, place in enumerate(st.session_state.places):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(place["name"])
                st.caption(f"ID: {place['id']}")
            with col2:
                if st.button("X", key=f"del_place_{idx}"):
                    st.session_state.places.pop(idx)
                    places_store.save(st.session_state.places)
                    st.rerun()
    else:
        st.info("No places added yet. Add one above!")

    st.divider()
    if st.button("Stop App", type="secondary", use_container_width=True,
                 help="Stop the Streamlit server"):
        chrome.kill_stale_processes()
        st.warning("Stopping server...")
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)


# Prerequisites

if not st.session_state.email_user or not st.session_state.email_pass:
    st.warning("Please configure your email in the sidebar first")
    st.stop()

if not st.session_state.places:
    st.warning("Please add at least one place in the sidebar")
    st.stop()


# Main controls

selected_place = st.selectbox(
    "Select Place to Book",
    options=range(len(st.session_state.places)),
    format_func=lambda i: f"{st.session_state.places[i]['name']} "
                          f"(ID: {st.session_state.places[i]['id']})",
)
res_id = st.session_state.places[selected_place]["id"]
email_user = st.session_state.email_user
email_pass = st.session_state.email_pass

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    today = datetime.now().date()
    start_date = st.date_input("Start Date", value=today + timedelta(days=1),
                               min_value=today)
with col2:
    mode = st.radio("Mode", ["Single", "Repeat (Week)"], horizontal=True)
    dates = [start_date]
    if "Repeat" in mode:
        curr = start_date + timedelta(days=1)
        while curr <= today + timedelta(days=7):
            dates.append(curr)
            curr += timedelta(days=1)
with col3:
    st.write("")

st.subheader("Time Slots")
for idx, slot in enumerate(st.session_state.time_slots):
    col_a, col_b, col_c = st.columns([3, 3, 1])
    with col_a:
        st.selectbox(f"Start {idx + 1}", ORARI,
                     format_func=lambda x: ORARI_DISPLAY[ORARI.index(x)],
                     index=ORARI.index(slot["start"]), key=f"start_{idx}",
                     on_change=on_start_change, args=(idx,))
    with col_b:
        if f"end_{idx}" not in st.session_state:
            st.session_state[f"end_{idx}"] = slot["end"]
        st.selectbox(f"End {idx + 1}", ORARI,
                     format_func=lambda x: ORARI_DISPLAY[ORARI.index(x)],
                     key=f"end_{idx}")
    with col_c:
        if len(st.session_state.time_slots) > 1:
            if st.button("X", key=f"remove_{idx}", help="Remove slot"):
                st.session_state.time_slots.pop(idx)
                st.rerun()

slot_btn_col1, slot_btn_col2, _ = st.columns([2, 2, 6])
with slot_btn_col1:
    if st.button("Add Slot", use_container_width=True):
        st.session_state.time_slots.append({"start": "09:00", "end": "13:00"})
        st.rerun()
with slot_btn_col2:
    if st.button("Reset Slots", use_container_width=True):
        st.session_state.time_slots = [{"start": "14:00", "end": "18:00"}]
        st.rerun()

st.divider()

btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 1])
with btn_col1:
    total_bookings = len(dates) * len(st.session_state.time_slots)
    launch_btn = st.button(f"LAUNCH ({total_bookings} bookings)", type="primary",
                           use_container_width=True)
with btn_col2:
    validate_btn = st.button("VALIDATE ONLY (Last 3h)", type="secondary",
                             use_container_width=True)
with btn_col3:
    delete_mail_btn = st.button("Clean Inbox", use_container_width=True,
                                help="Delete Affluences emails from last 7 days")


# launch!!!

if launch_btn:
    if not email_pass:
        st.error("No password.")
    else:
        with st.spinner("Cleaning up stale Chrome processes..."):
            chrome.kill_stale_processes()
            time.sleep(0.5)

        driver_path = get_driver_path()
        if not driver_path:
            st.error("Failed to load ChromeDriver")
            st.stop()
        if not chrome.find_chrome_binary():
            st.error("Chrome not found. Install Google Chrome and restart the app.")
            st.stop()

        booking_client = BookingClient(get_http_session())
        email_client = get_email_client()

        st.session_state.history = []
        for d in dates:
            for slot in st.session_state.time_slots:
                st.session_state.history.append({
                    "Date": d,
                    "DateStr": d.strftime("%Y-%m-%d"),
                    "TimeSlot": f"{slot['start']}-{slot['end']}",
                    "Status": "Pending",
                    "Confirmed": False,
                })

        dashboard = st.empty()
        dashboard.dataframe(pd.DataFrame(st.session_state.history))

        with st.status("Phase 1: API Requests (parallel)...", expanded=True) as status:
            tasks = []
            for i, record in enumerate(st.session_state.history):
                start, end = record["TimeSlot"].split("-")
                tasks.append((i, record["Date"], start, end))

            for batch_start in range(0, len(tasks), API_BATCH_SIZE):
                batch = tasks[batch_start:batch_start + API_BATCH_SIZE]
                with ThreadPoolExecutor(max_workers=API_BATCH_SIZE) as executor:
                    futures = {
                        executor.submit(booking_client.book_slot, email_user,
                                        d, start, end, res_id): i
                        for (i, d, start, end) in batch
                    }
                    for future in as_completed(futures):
                        i = futures[future]
                        ok, msg = future.result()
                        if ok:
                            st.session_state.history[i]["Status"] = "Sent"
                        else:
                            st.session_state.history[i]["Status"] = f"Error: {msg}"
                            st.session_state.history[i]["Confirmed"] = True

                dashboard.dataframe(pd.DataFrame(st.session_state.history))
                if batch_start + API_BATCH_SIZE < len(tasks):
                    time.sleep(random.uniform(0.2, 0.5))

            status.update(label="Requests sent.", state="complete")

        time.sleep(2)
        status_text = st.empty()
        start_time = time.time()
        timeout = 30

        try:
            while (time.time() - start_time) < timeout:
                pending = [i for i, r in enumerate(st.session_state.history)
                           if not r["Confirmed"]
                           and r["Status"] in ("Sent", "Retry...", "Validating...")]
                if not pending:
                    break

                status_text.write(
                    f"Checking inbox... ({int(timeout - (time.time() - start_time))}s left)")

                found = email_client.find_confirmations(hours=1, use_persistent=True)
                validation_tasks = []
                for reservation in found:
                    for idx in pending:
                        if st.session_state.history[idx]["Date"] == reservation.date:
                            st.session_state.history[idx]["Status"] = "Validating..."
                            validation_tasks.append({"index": idx, "link": reservation.link})

                dashboard.dataframe(pd.DataFrame(st.session_state.history))

                if validation_tasks:
                    status_text.write(f"Launching {len(validation_tasks)} selenium browsers...")
                    for res in _validate_links(validation_tasks, driver_path):
                        if res.success:
                            st.session_state.history[res.index]["Status"] = "CONFIRMED"
                            st.session_state.history[res.index]["Confirmed"] = True
                        else:
                            st.session_state.history[res.index]["Status"] = "Retry..."
                    dashboard.dataframe(pd.DataFrame(st.session_state.history))

                time.sleep(4)
        finally:
            email_client.close()

        status_text.success("Finished.")
        for i, r in enumerate(st.session_state.history):
            if not r["Confirmed"] and r["Status"] in ("Sent", "Retry...", "Validating..."):
                st.session_state.history[i]["Status"] = "Timeout"
        dashboard.dataframe(pd.DataFrame(st.session_state.history))
        st.success("Process completed")


# validation only

if validate_btn:
    if not email_pass:
        st.error("No password.")
    else:
        with st.spinner("Cleaning up stale Chrome processes..."):
            chrome.kill_stale_processes()
            time.sleep(0.5)

        driver_path = get_driver_path()
        if not driver_path:
            st.error("Failed to load ChromeDriver")
            st.stop()
        if not chrome.find_chrome_binary():
            st.error("Chrome not found. Install Google Chrome and restart the app.")
            st.stop()

        with st.spinner("Searching emails from last 3 hours..."):
            found = get_email_client().find_confirmations(hours=3)

        if not found:
            st.warning("No confirmation emails found in the last 3 hours.")
        else:
            st.info(f"Found {len(found)} confirmation email(s)")
            tasks = [{"index": idx, "link": r.link} for idx, r in enumerate(found)]
            dates_by_index = {idx: r.date for idx, r in enumerate(found)}

            progress_text = st.empty()
            progress_text.write(f"Validating {len(tasks)} reservation(s)...")

            validated, failed = [], []
            for res in _validate_links(tasks, driver_path):
                when = dates_by_index[res.index]
                if res.success:
                    validated.append({"Date": when, "Status": "VALIDATED"})
                else:
                    failed.append({"Date": when, "Status": "FAILED",
                                   "Error": res.error or "Unknown error"})

            if validated:
                st.success(f"Successfully validated {len(validated)} reservation(s)!")
                df = pd.DataFrame(validated)
                df["DateStr"] = df["Date"].apply(lambda x: x.strftime("%Y-%m-%d"))
                st.dataframe(df[["DateStr", "Status"]].style.map(
                    lambda x: "background-color: #d4edda; color: black"
                              if "VALIDATED" in str(x) else "",
                    subset=["Status"]), use_container_width=True)

            if failed:
                st.error(f"Failed to validate {len(failed)} reservation(s)")
                df = pd.DataFrame(failed)
                df["DateStr"] = df["Date"].apply(lambda x: x.strftime("%Y-%m-%d"))
                with st.expander("Show failed validations"):
                    st.dataframe(df[["DateStr", "Status", "Error"]],
                                 use_container_width=True)


# clean the inbox

if delete_mail_btn:
    if not email_pass:
        st.error("No password.")
    else:
        with st.spinner("Searching and deleting Affluences emails..."):
            found, deleted, error = get_email_client().delete_affluences_emails(days=7)

        if error:
            st.error(f"Error: {error}")
        elif found == 0:
            st.info("No Affluences emails found in the last 7 days")
        elif deleted == found:
            st.success(f"Found {found} email(s); deleted {deleted} successfully.")
        else:
            st.warning(f"Found {found} email(s); deleted {deleted} (some failed).")


# history table

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)[["DateStr", "TimeSlot", "Status"]]

    def color_rows(val):
        color = "white"
        if "CONFIRMED" in val or "VALIDATED" in val:
            color = "#d4edda"
        elif "Sent" in val:
            color = "#fff3cd"
        elif "Timeout" in val or "Not Reserved" in val or "Error" in val:
            color = "#f8d7da"
        return f"background-color: {color}; color: black"

    st.dataframe(df.style.map(color_rows, subset=["Status"]), use_container_width=True)
