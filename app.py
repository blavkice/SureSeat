import streamlit as st
import requests
import imaplib
import email
import re
import time
import random
import pandas as pd
import subprocess
import os
import signal
import json
import base64
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

IMAP_SERVER = "imap.gmail.com"
MAX_WORKERS = 5
PLACES_FILE = "places.json"

USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

ORARI = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]

# italian month names for email parsing
MONTHS_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

def load_places():
    try:
        if os.path.exists(PLACES_FILE):
            with open(PLACES_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_places(places):
    try:
        with open(PLACES_FILE, 'w') as f:
            json.dump(places, f, indent=2)
        return True
    except:
        return False

def _get_machine_key():
    import socket
    import getpass
    machine_id = f"{socket.gethostname()}-{getpass.getuser()}".encode()
    key = hashlib.sha256(machine_id).digest()
    return base64.urlsafe_b64encode(key)

def _encrypt(text):
    key = _get_machine_key()
    encrypted = bytearray()
    for i, char in enumerate(text.encode()):
        encrypted.append(char ^ key[i % len(key)])
    return base64.b64encode(encrypted).decode()

def _decrypt(encrypted_text):
    try:
        key = _get_machine_key()
        encrypted = base64.b64decode(encrypted_text.encode())
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key[i % len(key)])
        return decrypted.decode()
    except:
        return None

def load_email_credentials():
    try:
        creds_file = '.streamlit/.creds'
        if os.path.exists(creds_file):
            with open(creds_file, 'r') as f:
                content = json.load(f)
                email = _decrypt(content.get('email', ''))
                password = _decrypt(content.get('password', ''))
                if email and password:
                    return email, password
    except:
        pass
    return None, None

def save_email_credentials(email, password):
    try:
        os.makedirs('.streamlit', exist_ok=True)
        
        encrypted_data = {
            'email': _encrypt(email),
            'password': _encrypt(password)
        }
        
        with open('.streamlit/.creds', 'w') as f:
            json.dump(encrypted_data, f)
        return True
    except Exception as e:
        return False

def kill_stale_chrome_processes():
    try:
        if os.name == 'posix':
            subprocess.run(['killall', '-9', 'chrome'], stderr=subprocess.DEVNULL)
            subprocess.run(['killall', '-9', 'chromium'], stderr=subprocess.DEVNULL)
            subprocess.run(['killall', '-9', 'chromedriver'], stderr=subprocess.DEVNULL)
        elif os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], stderr=subprocess.DEVNULL)
            subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], stderr=subprocess.DEVNULL)
    except:
        pass

def aggiorna_fine(idx):
    try:
        slot = st.session_state.time_slots[idx]
        start_idx = ORARI.index(slot["start"])
        end_idx = (start_idx + 8) % len(ORARI)
        slot["end"] = ORARI[end_idx]
    except:
        pass

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS_LIST),
        'Content-Type': 'application/json',
        'Origin': 'https://affluences.com',
        'Referer': 'https://affluences.com/',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7'
    }

# core logic

def prenota_slot(user_email, data, ora_inizio, ora_fine, resource_id):
    url = f"https://reservation.affluences.com/api/reserve/{resource_id}"
    headers = get_random_headers()
    payload = {
        "email": user_email,
        "date": data.strftime("%Y-%m-%d"),
        "start_time": ora_inizio,
        "end_time": ora_fine,
        "person_count": 1,
        "note": "Reservation"
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code in [200, 201]: return True, "Sent"
        elif res.status_code == 400 and "quota" in res.text.lower(): return False, "Quota Limit"
        else: return False, f"Err {res.status_code}"
    except Exception as e: return False, "Conn Error"

def get_email_links(mail_user, mail_app_password):
    found_items = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(mail_user, mail_app_password)
        mail.select("inbox")

        status, messages = mail.search(None, '(UNSEEN FROM "no-reply@affluences.com")')
        if not messages[0]:
             status, messages = mail.search(None, '(UNSEEN FROM "Affluences")')
        
        mail_ids = messages[0].split()
        
        for email_id in mail_ids:
            _, data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload: body = payload.decode(errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload: body = payload.decode(errors="ignore")

            match_data = re.search(r'(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})', body, re.IGNORECASE)
            match_link = re.search(r'(https://affluences\.com.*?/reservation/confirm\?reservationToken=[a-zA-Z0-9-]+)', body)

            if match_link and match_data:
                giorno = int(match_data.group(1))
                mese_str = match_data.group(2).lower()
                anno = int(match_data.group(3))
                mese = MONTHS_IT.get(mese_str, 0)
                
                try:
                    data_obj = datetime(anno, mese, giorno).date()
                    link_pulito = match_link.group(1).replace("&amp;", "&")
                    found_items.append({'date': data_obj, 'link': link_pulito})
                except: pass
        
        return found_items
    except Exception as e:
        return []

def get_recent_email_links(mail_user, mail_app_password, hours=3):
    found_items = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(mail_user, mail_app_password)
        mail.select("inbox")

        since_date = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
        
        status, messages = mail.search(None, f'(SINCE {since_date} FROM "no-reply@affluences.com")')
        if not messages[0]:
            status, messages = mail.search(None, f'(SINCE {since_date} FROM "Affluences")')
        
        mail_ids = messages[0].split()
        
        for email_id in mail_ids:
            _, data = mail.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload: body = payload.decode(errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload: body = payload.decode(errors="ignore")

            match_data = re.search(r'(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})', body, re.IGNORECASE)
            match_link = re.search(r'(https://affluences\.com.*?/reservation/confirm\?reservationToken=[a-zA-Z0-9-]+)', body)

            if match_link and match_data:
                giorno = int(match_data.group(1))
                mese_str = match_data.group(2).lower()
                anno = int(match_data.group(3))
                mese = MONTHS_IT.get(mese_str, 0)
                
                try:
                    data_obj = datetime(anno, mese, giorno).date()
                    link_pulito = match_link.group(1).replace("&amp;", "&")
                    found_items.append({'date': data_obj, 'link': link_pulito})
                except: pass
        
        return found_items
    except Exception as e:
        return []

def selenium_worker(task_data):
    """
    Worker ottimizzato: riceve il driver_path già pronto.
    Aggiunto retry logic per gestire daemon conflicts.
    """
    link = task_data['link']
    idx = task_data['index']
    driver_path = task_data['driver_path']
    
    driver = None
    retry_count = 0
    max_retries = 2
    
    while retry_count <= max_retries:
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless") 
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # Disabilita immagini e GPU per velocità estrema
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
            chrome_options.add_argument("--disable-extensions")  # Evita conflitti daemon
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS_LIST)}")

            # Usa il driver già scaricato, niente check online
            service = Service(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Timeout più lungo per pagine lente
            driver.set_page_load_timeout(20)
            driver.set_script_timeout(20)
            
            # Carica la pagina
            driver.get(link)
            
            # Aspetta che la pagina sia completamente caricata
            wait = WebDriverWait(driver, 15)
            
            try:
                # Cerca vari tipi di pulsanti/link di conferma
                # Prova diversi selettori in ordine
                button_selectors = [
                    "//a[contains(@href, 'confirm') or contains(@href, 'conferma')]",
                    "//button[contains(text(), 'Conferma') or contains(text(), 'Confirm')]",
                    "//a[contains(text(), 'Conferma') or contains(text(), 'Confirm')]",
                    "//input[@type='submit' and (contains(@value, 'Conferma') or contains(@value, 'Confirm'))]",
                    "//*[@role='button' and (contains(text(), 'Conferma') or contains(text(), 'Confirm'))]"
                ]
                
                btn = None
                for selector in button_selectors:
                    try:
                        btn = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                        # Scroll al pulsante per sicurezza
                        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        time.sleep(0.5)
                        # Attendi che sia cliccabile
                        btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        break
                    except:
                        continue
                
                if btn:
                    btn.click()
                    # Aspetta redirect/conferma
                    time.sleep(3)
                    
                    # Verifica successo nella pagina risultante
                    page_content = driver.page_source.lower()
                    if any(keyword in page_content for keyword in ["success", "confermata", "confirmed", "validata", "prenotazione confermata"]):
                        return {'index': idx, 'success': True}
                    else:
                        return {'index': idx, 'success': False, 'error': 'No success confirmation after click'}
                else:
                    # Nessun pulsante trovato - controlla se già confermata
                    page_content = driver.page_source.lower()
                    if any(keyword in page_content for keyword in ["già confermata", "already confirmed", "prenotazione confermata"]):
                        return {'index': idx, 'success': True}
                    return {'index': idx, 'success': False, 'error': 'Confirm button not found'}
                    
            except Exception as btn_error:
                # Fallback: controlla se la pagina mostra già la conferma
                page_content = driver.page_source.lower()
                if any(keyword in page_content for keyword in ["già confermata", "already confirmed", "success", "confermata"]):
                    return {'index': idx, 'success': True}
                return {'index': idx, 'success': False, 'error': f'Error: {str(btn_error)[:100]}'}
            
        except Exception as e:
            # Retry logic for daemon conflicts
            if retry_count < max_retries and (("chrome" in str(e).lower()) or ("connection" in str(e).lower())):
                retry_count += 1
                if driver:
                    try: driver.quit()
                    except: pass
                time.sleep(0.5)  # Brief wait before retry
                continue
            return {'index': idx, 'success': False, 'error': str(e)}
        finally:
            if driver: 
                try: driver.quit()
                except: pass
        break

st.set_page_config(page_title="SureSeat", layout="wide")
st.title("SureSeat")

if "history" not in st.session_state: st.session_state.history = []
if "time_slots" not in st.session_state: st.session_state.time_slots = [{"start": "14:00", "end": "18:00"}]
if "places" not in st.session_state: 
    st.session_state.places = load_places()
if "email_user" not in st.session_state: 
    st.session_state.email_user = ""
if "email_pass" not in st.session_state: 
    st.session_state.email_pass = ""

if not st.session_state.email_user or not st.session_state.email_pass:
    loaded_email, loaded_pass = load_email_credentials()
    if loaded_email and loaded_pass:
        st.session_state.email_user = loaded_email
        st.session_state.email_pass = loaded_pass

with st.sidebar:
    st.header("Configuration")
    
    # Email Configuration
    with st.expander("Email Settings", expanded=not st.session_state.email_user):
        email_user = st.text_input("Gmail Address", value=st.session_state.email_user, key="email_input")
        email_pass = st.text_input("App Password", value=st.session_state.email_pass, type="password", key="pass_input", 
                                   help="Generate at: https://myaccount.google.com/apppasswords")
        
        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button("Save", use_container_width=True):
                if email_user and email_pass:
                    st.session_state.email_user = email_user
                    st.session_state.email_pass = email_pass
                    
                    if save_email_credentials(email_user, email_pass):
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
    
    # Places Management
    st.subheader("Places")
    
    with st.expander("Add New Place", expanded=len(st.session_state.places) == 0):
        st.markdown("""
        Find Resource ID:
        1. Go to affluences.com
        2. Book any seat
        3. Copy ID from URL: affluences.com/reservation/12345
        """)
        
        place_name = st.text_input("Place Name", placeholder="e.g., Sala Inglese - Posto 217", key="new_place_name")
        place_id = st.text_input("Resource ID", placeholder="e.g., 20530", key="new_place_id")
        
        if st.button("Add Place", use_container_width=True):
            if place_name and place_id:
                st.session_state.places.append({"name": place_name, "id": place_id})
                if save_places(st.session_state.places):
                    st.success(f"Added & Saved: {place_name}")
                else:
                    st.warning(f"Added (but failed to save to file): {place_name}")
                st.rerun()
            else:
                st.error("Please fill both fields")
    
    # Display saved places
    if st.session_state.places:
        for idx, place in enumerate(st.session_state.places):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(place['name'])
                st.caption(f"ID: {place['id']}")
            with col2:
                if st.button("X", key=f"del_place_{idx}"):
                    st.session_state.places.pop(idx)
                    save_places(st.session_state.places)
                    st.rerun()
    else:
        st.info("No places added yet. Add one above!")
    
    st.divider()
    if st.button("Stop App", type="secondary", use_container_width=True, help="Stop the Streamlit server"):
        kill_stale_chrome_processes()
        st.warning("Stopping server...")
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

# Main area - check prerequisites
if not st.session_state.email_user or not st.session_state.email_pass:
    st.warning("Please configure your email in the sidebar first")
    st.stop()

if not st.session_state.places:
    st.warning("Please add at least one place in the sidebar")
    st.stop()

# Place selector
selected_place = st.selectbox(
    "Select Place to Book",
    options=range(len(st.session_state.places)),
    format_func=lambda i: f"{st.session_state.places[i]['name']} (ID: {st.session_state.places[i]['id']})"
)
res_id = st.session_state.places[selected_place]["id"]
email_user = st.session_state.email_user
email_pass = st.session_state.email_pass

col1, col2, col3 = st.columns([1,1,2])
with col1:
    today = datetime.now().date()
    start_date = st.date_input("Start Date", value=today + timedelta(days=1), min_value=today)
with col2:
    mode = st.radio("Mode", ["Single", "Repeat (Week)"], horizontal=True)
    dates = [start_date]
    if "Repeat" in mode:
        curr = start_date + timedelta(days=1)
        while curr <= today + timedelta(days=7):
            dates.append(curr)
            curr += timedelta(days=1)
with col3:
    st.write("") # spacing

# Time Slots Section
st.subheader("Time Slots")
slot_cols = st.columns([3, 3, 1])

for idx, slot in enumerate(st.session_state.time_slots):
    col_a, col_b, col_c = st.columns([3, 3, 1])
    with col_a:
        slot["start"] = st.selectbox(f"Start {idx+1}", ORARI, index=ORARI.index(slot["start"]), key=f"start_{idx}", on_change=aggiorna_fine, args=(idx,))
    with col_b:
        slot["end"] = st.selectbox(f"End {idx+1}", ORARI, index=ORARI.index(slot["end"]), key=f"end_{idx}")
    with col_c:
        if len(st.session_state.time_slots) > 1:
            if st.button("X", key=f"remove_{idx}", help="Remove slot"):
                st.session_state.time_slots.pop(idx)
                st.rerun()

slot_btn_col1, slot_btn_col2, slot_btn_col3 = st.columns([2, 2, 6])
with slot_btn_col1:
    if st.button("Add Slot", use_container_width=True):
        st.session_state.time_slots.append({"start": "09:00", "end": "13:00"})
        st.rerun()
with slot_btn_col2:
    if st.button("Reset Slots", use_container_width=True):
        st.session_state.time_slots = [{"start": "14:00", "end": "18:00"}]
        st.rerun()

st.divider()

# Buttons side by side
btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    total_bookings = len(dates) * len(st.session_state.time_slots)
    launch_btn = st.button(f"LAUNCH ({total_bookings} bookings)", type="primary", use_container_width=True)
with btn_col2:
    validate_btn = st.button("VALIDATE ONLY (Last 3h)", type="secondary", use_container_width=True)

if launch_btn:
        if not email_pass:
            st.error("No password.")
        else:
            with st.spinner("Cleaning up stale Chrome processes..."):
                kill_stale_chrome_processes()
                time.sleep(1)
            
            with st.spinner("Pre-loading Chrome Driver..."):
                try:
                    cached_driver_path = ChromeDriverManager().install()
                except Exception as e:
                    st.error(f"Failed to load driver: {e}")
                    st.stop()

            st.session_state.history = []
            for d in dates:
                for slot_idx, slot in enumerate(st.session_state.time_slots):
                    st.session_state.history.append({
                        "Date": d, 
                        "DateStr": d.strftime("%Y-%m-%d"),
                        "TimeSlot": f"{slot['start']}-{slot['end']}",
                        "Status": "Pending", 
                        "Confirmed": False
                    })
            
            dashboard = st.empty()
            dashboard.dataframe(pd.DataFrame(st.session_state.history))
            
            with st.status("Phase 1: API Requests...", expanded=True) as status:
                for i, record in enumerate(st.session_state.history):
                    d = record["Date"]
                    time_parts = record["TimeSlot"].split("-")
                    slot_start = time_parts[0]
                    slot_end = time_parts[1]
                    
                    ok, msg = prenota_slot(email_user, d, slot_start, slot_end, res_id)
                    if ok:
                        st.session_state.history[i]["Status"] = "Sent"
                    else:
                        st.session_state.history[i]["Status"] = f"Error: {msg}"
                        st.session_state.history[i]["Confirmed"] = True 
                    
                    dashboard.dataframe(pd.DataFrame(st.session_state.history))
                    time.sleep(random.uniform(0.3, 1.0))
                status.update(label="Requests sent.", state="complete")

            time.sleep(4) 

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            start_time = time.time()
            timeout = 30 
            
            while (time.time() - start_time) < timeout:
                pending_indices = [i for i, r in enumerate(st.session_state.history) 
                                   if not r["Confirmed"] and "Sent" in r["Status"]]
                
                if not pending_indices: break

                status_text.write(f"Checking inbox... ({int(timeout - (time.time()-start_time))}s left)")
                
                found_emails = get_email_links(email_user, email_pass)
                
                tasks = []
                for email_item in found_emails:
                    m_date = email_item['date']
                    m_link = email_item['link']
                    
                    for idx in pending_indices:
                        rec = st.session_state.history[idx]
                        if rec["Date"] == m_date:
                            st.session_state.history[idx]["Status"] = "Validating..."
                            tasks.append({'index': idx, 'link': m_link, 'driver_path': cached_driver_path})
                
                dashboard.dataframe(pd.DataFrame(st.session_state.history))
                
                if tasks:
                    status_text.write(f"Launching {len(tasks)} selenium browsers...")
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                        futures = {executor.submit(selenium_worker, t): t for t in tasks}
                        
                        for future in as_completed(futures):
                            res = future.result()
                            idx = res['index']
                            if res['success']:
                                st.session_state.history[idx]["Status"] = "CONFIRMED"
                                st.session_state.history[idx]["Confirmed"] = True
                            else:
                                st.session_state.history[idx]["Status"] = "Retry..."
                    
                    dashboard.dataframe(pd.DataFrame(st.session_state.history))
                
                time.sleep(3)

            status_text.success("Finished.")
            
            for i, r in enumerate(st.session_state.history):
                if not r["Confirmed"] and "Sent" in r["Status"]:
                     st.session_state.history[i]["Status"] = "Timeout"
            dashboard.dataframe(pd.DataFrame(st.session_state.history))
            st.balloons()

# Validate only mode
if validate_btn:
    if not email_pass:
        st.error("No password.")
    else:
        with st.spinner("Cleaning up stale Chrome processes..."):
            kill_stale_chrome_processes()
            time.sleep(1)
        
        with st.spinner("Loading Chrome Driver..."):
            try:
                cached_driver_path = ChromeDriverManager().install()
            except Exception as e:
                st.error(f"Failed to load driver: {e}")
                st.stop()
        
        with st.spinner("Searching emails from last 3 hours..."):
            found_emails = get_recent_email_links(email_user, email_pass, hours=3)
        
        if not found_emails:
            st.warning("No confirmation emails found in the last 3 hours.")
        else:
            st.info(f"Found {len(found_emails)} confirmation email(s)")
            
            # Create validation tasks
            validated_results = []
            failed_results = []
            tasks = []
            for idx, email_item in enumerate(found_emails):
                tasks.append({
                    'index': idx,
                    'link': email_item['link'],
                    'driver_path': cached_driver_path,
                    'date': email_item['date']
                })
            
            progress_text = st.empty()
            progress_text.write(f"Validating {len(tasks)} reservation(s)...")
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(selenium_worker, t): t for t in tasks}
                
                for future in as_completed(futures):
                    task = futures[future]
                    res = future.result()
                    
                    if res['success']:
                        validated_results.append({
                            'Date': task['date'],
                            'Status': 'VALIDATED'
                        })
                    else:
                        failed_results.append({
                            'Date': task['date'],
                            'Status': 'FAILED',
                            'Error': res.get('error', 'Unknown error')
                        })
            
            if validated_results:
                st.success(f"Successfully validated {len(validated_results)} reservation(s)!")
                df_validated = pd.DataFrame(validated_results)
                df_validated['DateStr'] = df_validated['Date'].apply(lambda x: x.strftime("%Y-%m-%d"))
                st.dataframe(df_validated[['DateStr', 'Status']].style.map(
                    lambda x: 'background-color: #d4edda; color: black' if 'VALIDATED' in str(x) else '', 
                    subset=['Status']
                ), use_container_width=True)
                st.balloons()
            
            if failed_results:
                st.error(f"Failed to validate {len(failed_results)} reservation(s)")
                df_failed = pd.DataFrame(failed_results)
                df_failed['DateStr'] = df_failed['Date'].apply(lambda x: x.strftime("%Y-%m-%d"))
                with st.expander("Show failed validations"):
                    st.dataframe(df_failed[['DateStr', 'Status', 'Error']], use_container_width=True)
            
            if not validated_results and not failed_results:
                st.warning("No reservations were processed.")

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)[["DateStr", "TimeSlot", "Status"]]
    def color_rows(val):
        color = 'white'
        if 'CONFIRMED' in val: color = '#d4edda'
        elif 'Sent' in val: color = '#fff3cd'
        elif 'Timeout' in val or 'Error' in val: color = '#f8d7da'
        return f'background-color: {color}; color: black'
    st.dataframe(df.style.map(color_rows, subset=['Status']), use_container_width=True)
