# Ria Free V3

A free local MVP for Ricky Davies Tattoos.

## Included
- Mobile-first dashboard
- Three-way message routing
- Tattoo enquiry flow
- Real Mon-Fri availability
- Wednesday half-day £300
- Mon/Tue/Thu/Fri full-day £450
- £50 deposit
- 10:00 AM start
- Double-booking protection
- Customer details only after a date is chosen
- Provisional booking -> deposit -> confirmed
- Customer search
- Enquiry status management
- SQLite database
- Meta and Stripe placeholders

## Run on a Mac
1. Install Python 3
2. Open Terminal in this folder
3. Run:
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app:app --reload
4. Open http://127.0.0.1:8000

Instagram and Stripe are not live yet.
Do not paste passwords or API secrets into chat.
