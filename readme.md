# SureSeat

Automated reservation system targeting the Affluences booking platform. After deconstructing the API endpoints and reverse-engineering the booking flow, I built this tool to bypass the manual UI workflow entirely as it was so boring to use

**Technical Approach**: Intercepted and analyzed the booking POST requests to identify required parameters and authentication patterns. Implemented direct API interaction bypassing the web interface, combined with IMAP-based email scraping for confirmation token extraction.

**Security Implementation**: Machine-specific credential encryption using XOR cipher with SHA256-derived keys tied to hostname+username. All sensitive data encrypted at rest, no plaintext credentials in version control.

## Capabilities

- Direct API booking via reverse-engineered endpoints
- Automated email confirmation harvesting (IMAP search with Italian date parsing)
- Concurrent validation using headless Chrome instances (ThreadPoolExecutor)
- Hardware-tied credential encryption (machine-specific decryption keys)
- Persistent state management with JSON storage
- Built-in rate limiting and daemon conflict resolution

## Installation

### Prerequisites

- Python 3.8+
- Chrome browser installed
- Gmail account with App Password

### Installation

1. Clone the repository:
```bash
git clone https://github.com/blavkice/SureSeat.git
cd sureseat
```

2. Install dependencies:
```bash
pip install streamlit selenium webdriver-manager requests pandas
```

3. Run the app:
```bash
streamlit run app.py
```

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

- **Language**: Currently only works with Italian emails (date parsing looks for "gennaio", "febbraio", etc.)
- **Rate Limiting**: The app includes delays between requests to avoid rate limiting
- **Quota**: Affluences has booking quotas - respect their limits
- **Email**: Only works with Gmail (uses IMAP)
- **Browser**: Requires Chrome/Chromium installed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use and modify

## Disclaimer

This tool is for personal use only. Please respect Affluences' terms of service and booking policies. Use responsibly and don't abuse the automation features.bash
pip install selenium webdriver-manager streamlit requests
