# SureSeat

Automated reservation system targeting the Affluences booking platform. After deconstructing the API endpoints and reverse-engineering the booking flow, I built this tool to bypass the manual UI workflow entirely as it was so boring to use

**Technical Approach**: Intercepted and analyzed the booking POST requests to identify required parameters and authentication patterns. Implemented direct API interaction bypassing the web interface, combined with IMAP-based email scraping for confirmation token extraction.

**Credential Storage**: The Gmail app password is not stored in plaintext. It is obfuscated with a XOR cipher keyed on a SHA-256 of `hostname + username` and saved base64-encoded under `.streamlit/.creds`. This keeps secrets out of version control and ties the file to the machine that wrote it, but it is **obfuscation**, not strong cryptography: anyone with read access to that machine can recover the password. Treat the credentials file as sensitive, and prefer a dedicated Gmail app password that you can revoke.

## Capabilities

- Direct API booking via reverse-engineered endpoints
- Automated email confirmation harvesting (IMAP search with multilingual date parsing)
- Concurrent validation using headless Chrome instances (ThreadPoolExecutor)
- Machine-tied credential obfuscation (no plaintext password on disk)
- Persistent state management with JSON storage
- Built-in rate limiting and daemon conflict resolution
- HTTP connection pooling for faster API requests
- Persistent IMAP connections for efficient email polling
- Inbox cleanup for Affluences emails

## Project Structure

The logic is split into a small package, keeping `app.py` as a thin UI layer:

```
app.py                      Streamlit UI and flow orchestration
sureseat/
  config.py                 Constants and environment-driven configuration
  i18n.py                   Multilingual month / keyword tables (from CSV)
  crypto.py                 Machine-tied credential storage
  storage.py                Saved places persistence
  chrome.py                 Chrome/Chromium discovery and headless options
  booking/
    api.py                  Affluences reservation HTTP client
    email_client.py         IMAP confirmation harvesting and inbox cleanup
    validator.py            Headless-Chrome confirmation of reservation links
```

## Installation

### Prerequisites

- Python 3.8+
- Chrome or Chromium browser installed
- Gmail account with App Password

### Local install

1. Clone the repository:

```bash
git clone https://github.com/blavkice/SureSeat.git
cd SureSeat
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
streamlit run app.py
```

The app is then available at http://localhost:8501.

## Running with Docker

Docker bundles Python, Chromium and the matching driver, so nothing needs to be
installed on the host beyond Docker itself.

### With Docker Compose (recommended)

```bash
docker compose up --build
```

Open http://localhost:8501. Saved places and encrypted credentials are written
to a local `./data` directory (created on first run) so they survive restarts.

### With plain Docker

```bash
docker build -t sureseat .
docker run -p 8501:8501 -v "$(pwd)/data:/app/data" \
  -e SURESEAT_PLACES_FILE=/app/data/places.json \
  -e SURESEAT_CREDS_FILE=/app/data/.creds \
  sureseat
```

### Configuration via environment variables


| Variable               | Default             | Purpose                                |
| ---------------------- | ------------------- | -------------------------------------- |
| `CHROME_BINARY`        | autodetected        | Path to the Chrome/Chromium binary     |
| `CHROMEDRIVER_PATH`    | webdriver-manager   | Path to a preinstalled chromedriver    |
| `SURESEAT_PLACES_FILE` | `places.json`       | Where saved places are stored          |
| `SURESEAT_CREDS_FILE`  | `.streamlit/.creds` | Where encrypted credentials are stored |
| `SURESEAT_IMAP_SERVER` | `imap.gmail.com`    | IMAP server for email polling          |
| `SURESEAT_MAX_WORKERS` | `5`                 | Parallel Selenium validation workers   |

Inside Docker, `CHROME_BINARY` and `CHROMEDRIVER_PATH` are preset to the system
Chromium, so no driver is downloaded at runtime.

> Note: credentials are encrypted with a key derived from hostname + user. The
> Compose file pins the container hostname so the encrypted file stays readable
> across rebuilds.

## Configuration

### Email Setup

Email credentials are saved securely in `.streamlit/.creds` with encryption based on your system.

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Generate a new app password
3. In SureSeat sidebar, enter your Gmail and App Password
4. Click "Save"

**Note:** Credentials are encrypted and automatically loaded on app start. They are tied to your machine.

### Adding Places (Resources)

Places are automatically saved to `places.json` and persist across sessions.

1. Open the "Add New Place" section in sidebar
2. Find your Resource ID:
   - Go to [Affluences](https://affluences.com)
   - Search and book any seat/resource
   - Look at the URL: `affluences.com/reservation/12345`
   - The number `12345` is your Resource ID
3. Enter a name (e.g., "Library - Desk 42")
4. Enter the Resource ID
5. Click "Add Place"

## Usage

### Basic Booking

1. **Select Place**: Choose from your saved places
2. **Set Date**: Pick start date (defaults to tomorrow)
3. **Choose Mode**:
   - "Single": Book only the selected date
   - "Repeat (Week)": Book for the next 7 days
4. **Configure Time Slots**: Add multiple slots per day if needed
5. **Click LAUNCH**: The bot will:
   - Send booking requests
   - Monitor your email for confirmations
   - Automatically validate bookings

### Validation Only

If you have pending reservations that need validation:

1. Click "VALIDATE ONLY (Last 3h)"
2. The bot will search your emails from the last 3 hours
3. Automatically validates all found confirmations
4. Shows success/failure report

### Clean Inbox

To delete Affluences emails cluttering your inbox:

1. Click "Clean Inbox"
2. Deletes all Affluences emails from the last 7 days
3. Removes both confirmation requests and confirmed booking emails

### Multiple Time Slots

To book multiple slots per day (e.g., morning + afternoon):

1. Configure first slot (e.g., 09:00 - 13:00)
2. Click "Add Slot"
3. Configure second slot (e.g., 14:00 - 18:00)
4. The bot will book both slots for each selected date

## Troubleshooting

### Chrome Issues

If you encounter Chrome daemon conflicts:

- The app automatically kills stale Chrome processes before starting
- If issues persist, click "Close App" in sidebar to clean up

### Email Not Receiving Confirmations

- Check spam folder
- Ensure App Password is correct
- Verify Gmail account has IMAP enabled

### Booking Failures

- Verify Resource ID is correct
- Check if the resource is available for booking
- Ensure you're within quota limits

## Notes

- **Language**: Supports 10 languages (English, Spanish, French, Portuguese, German, Italian, Dutch, Polish, Russian, Turkish). Configuration files:
  - `months.csv` - month names for email date parsing
  - `keywords.csv` - button labels and success messages for web scraping
- **Rate Limiting**: The app includes delays between requests to avoid rate limiting
- **Quota**: Affluences has booking quotas - respect their limits
- **Email**: Only works with Gmail (uses IMAP)
- **Browser**: Requires Chrome/Chromium installed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use and modify

## Disclaimer

This tool is for personal use only. Please respect Affluences' terms of service and booking policies. Use responsibly and don't abuse the automation features.
