from quart import Quart, request, render_template, redirect, url_for, session, send_file, make_response
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
import os
import json
import logging
import tempfile
from datetime import datetime
import atexit

import firebase_admin
from firebase_admin import credentials, firestore

from config import api_id, api_hash

app = Quart(__name__)
app.secret_key = 'your_secret_key'  # Change this to a random secret key

# Set up basic configuration for logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey.json')  # Path to your Firebase service account key
firebase_admin.initialize_app(cred)
db = firestore.client()  # Initialize Firestore

# Dictionary to store client instances for each user
clients = {}
SESSION_FILE = 'sessions.json'  # JSON file to store sessions

# Function to clean up temporary files
def cleanup_temp_files():
    for filename in os.listdir('downloads'):
        if filename.startswith('attachment_'):
            os.remove(os.path.join('downloads', filename))

# Register the cleanup function to run at exit
atexit.register(cleanup_temp_files)

async def load_session(user_id):
    try:
        doc_ref = db.collection('sessions').document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('session_string', '')
        return ''
    except Exception as e:
        logging.error(f"Error loading session: {e}")
        return ''

async def save_session(user_id, session_string):
    try:
        doc_ref = db.collection('sessions').document(user_id)
        doc_ref.set({'session_string': session_string})
    except Exception as e:
        logging.error(f"Error saving session: {e}")

async def initialize_client(user_id):
    if user_id in clients and clients[user_id].is_connected():
        return clients[user_id]

    session_string = await load_session(user_id)
    if session_string:
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        try:
            await client.connect()
            await client.get_me()  # Verify connection
            clients[user_id] = client
            return client
        except Exception:
            await logout_user(user_id)
            return None
    else:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        clients[user_id] = client
        return client

async def send_code(phone_number):
    try:
        client = await initialize_client(phone_number)
        if client is None:
            raise RuntimeError("Failed to initialize Telegram client.")
        
        await client.send_code_request(phone=phone_number)
        logging.info("Verification code sent successfully.")
    except Exception as e:
        logging.error(f"Error sending code request: {e}")
        raise

@app.errorhandler(Exception)
async def handle_exception(e):
    logging.error(f"An error occurred: {e}")
    response = {
        "error": "An unexpected error occurred. Please try again later."
    }
    return await make_response(json.dumps(response), 500, {"Content-Type": "application/json"})

@app.route('/', methods=['GET', 'POST'])
async def index():
    if 'logged_in' in session:
        user_id = session.get('phone_number')
        logging.info(f"Attempting to initialize client for user: {user_id}")
        if await initialize_client(user_id):
            logging.info("Client initialized successfully")
            return redirect(url_for('dashboard'))
        else:
            logging.info("Failed to initialize client")
            session.pop('logged_in', None)
            session.pop('username', None)

    if request.method == 'POST':
        form = await request.form
        phone_number = form['phone_number']
        session['phone_number'] = phone_number

        logging.info(f"Received phone number: {phone_number}")
        existing_session_string = await load_session(phone_number)
        if existing_session_string:
            logging.info("Session string found. Trying to connect...")
            client = TelegramClient(StringSession(existing_session_string), api_id, api_hash)
            await client.connect()
            try:
                await client.get_me()
                session['logged_in'] = True
                session['username'] = (await client.get_me()).first_name
                logging.info("User logged in successfully")
                return redirect(url_for('dashboard'))
            except Exception as e:
                logging.error(f"Error during login: {e}")
                await logout_user(phone_number)
                session.pop('logged_in', None)
                session.pop('username', None)
                return redirect(url_for('verify'))
        else:
            logging.info("No existing session found. Sending code...")
            await send_code(phone_number)
            return redirect(url_for('verify'))

    return await render_template('index.html')

@app.route('/verify', methods=['GET', 'POST'])
async def verify():
    if request.method == 'POST':
        form = await request.form
        code = form['code']
        session['code'] = code
        phone_number = session.get('phone_number')

        async def verify_code(phone_number, code):
            try:
                client = await initialize_client(phone_number)
                await client.sign_in(phone_number, code)
                session_string = client.session.save()
                await save_session(phone_number, session_string)
                session['logged_in'] = True
                session['username'] = (await client.get_me()).first_name
                return redirect(url_for('dashboard'))
            except SessionPasswordNeededError:
                return redirect(url_for('two_factor'))
            except Exception as e:
                logging.error(f"Error during verification: {e}")
                return f"Error: {str(e)}"

        message = await verify_code(phone_number, code)
        return message

    return await render_template('verify.html')

@app.route('/two_factor', methods=['GET', 'POST'])
async def two_factor():
    if request.method == 'POST':
        form = await request.form
        password = form['password']
        phone_number = session.get('phone_number')

        async def login_with_2fa():
            try:
                client = await initialize_client(phone_number)
                await client.sign_in(password=password)
                session['logged_in'] = True
                session['username'] = (await client.get_me()).first_name
                session_string = client.session.save()
                await save_session(phone_number, session_string)
                return redirect(url_for('dashboard'))
            except Exception as e:
                logging.error(f"Error during 2FA login: {e}")
                return f"Error: {str(e)}"

        message = await login_with_2fa()
        return message

    return await render_template('two_factor.html')

@app.route('/dashboard', methods=['GET', 'POST'])
async def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('index'))

    user_id = session.get('phone_number')
    client = await initialize_client(user_id)
    if not client or not client.is_connected():
        return redirect(url_for('index'))

    username = session.get('username')

    if request.method == 'POST':
        form = await request.form
        if 'message' in form:
            message = form['message']
            if message:
                await send_message(message)
        
        if 'file' in await request.files:
            uploaded_file = await request.files
            file = uploaded_file.get('file')
            if file:
                file_path = os.path.join('uploads', file.filename)
                await file.save(file_path)
                await upload_file(file_path)
                os.remove(file_path)

    return await render_template('dashboard.html', username=username)

async def send_message(message):
    user_id = session.get('phone_number')
    try:
        client = await initialize_client(user_id)
        if client and client.is_connected():
            me = await client.get_me()
            await client.send_message(me, message)
            return "Message sent!"
        else:
            return "Error: Client is not connected."
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return "Error: Failed to send message."

async def upload_file(file_path):
    user_id = session.get('phone_number')
    try:
        client = await initialize_client(user_id)
        if client and client.is_connected():
            me = await client.get_me()
            filename = os.path.basename(file_path)
            timestamp = datetime.now().isoformat()
            caption = f"Uploaded File: {filename}\nUploaded On: {timestamp}"
            await client.send_file(me, file_path, caption=caption)
            return "File sent!"
        else:
            return "Error: Client is not connected."
    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        return "Error: Failed to upload file."

async def logout_user(user_id):
    if user_id in clients:
        client = clients.pop(user_id)
        if client.is_connected():
            try:
                # Log out from Telegram servers
                await client.log_out()
            except Exception as e:
                logging.error(f"Error during logout from Telegram servers: {e}")
            
            # Disconnect the client
            await client.disconnect()

    session.clear()
    try:
        doc_ref = db.collection('sessions').document(user_id)
        doc_ref.delete()
    except Exception as e:
        logging.error(f"Error deleting session from Firestore: {e}")


@app.route('/logout')
async def logout():
    user_id = session.get('phone_number')
    await logout_user(user_id)
    return redirect(url_for('index'))

@app.route('/attachments', methods=['GET'])
async def attachments():
    if 'logged_in' not in session:
        return redirect(url_for('index'))

    # Pagination parameters
    per_page = 20
    page = int(request.args.get('page', 1))
    
    # Ensure the page number is valid
    if page < 1:
        page = 1

    attachments_list = []
    user_id = session.get('phone_number')
    client = await initialize_client(user_id)
    username = session.get('username')
    
    if client and client.is_connected():
        skip_count = (page - 1) * per_page
        fetched_count = 0
        total_count = 0
        messages_to_fetch = 100

        # Count total attachments
        async for message in client.iter_messages('me', limit=messages_to_fetch):
            if message.message.startswith("Uploaded File:"):
                total_count += 1

        total_pages = (total_count + per_page - 1) // per_page

        # Fetch messages with pagination
        async for message in client.iter_messages('me', limit=messages_to_fetch):
            if message.message.startswith("Uploaded File:"):
                if skip_count > 0:
                    skip_count -= 1
                else:
                    if fetched_count < per_page:
                        lines = message.message.splitlines()
                        filename = lines[0].replace("Uploaded File: ", "")
                        timestamp = lines[1].replace("Uploaded On: ", "")
                        
                         # Format the timestamp
                        try:
                            iso_format = "%Y-%m-%dT%H:%M:%S.%f"
                            dt = datetime.strptime(timestamp, iso_format)
                            timestamp = dt.strftime("%B %d, %Y at %I:%M %p")
                        except ValueError:
                            timestamp = timestamp
                        
                        file_extension = os.path.splitext(filename)[1].lower()
                        attachments_list.append((filename, timestamp, message.id, file_extension))
                        fetched_count += 1
                    else:
                        break

    return await render_template('attachments.html', attachments=attachments_list, page=page, per_page=per_page, total_pages=total_pages, username=username)

@app.route('/download/<int:message_id>', methods=['GET'])
async def download(message_id):
    if 'logged_in' not in session:
        return redirect(url_for('index'))

    user_id = session.get('phone_number')
    client = await initialize_client(user_id)
    if client and client.is_connected():
        try:
            message = await client.get_messages('me', ids=message_id)
            if message.media:
                lines = message.message.splitlines()
                filename = lines[0].replace("Uploaded File: ", "")
                full_filename = filename

                with tempfile.NamedTemporaryFile(dir='downloads', prefix='attachment_', delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    await client.download_media(message, temp_file_path)

                return await send_file(temp_file_path, as_attachment=True, attachment_filename=full_filename)
            else:
                return "No media found in the message."
        except Exception as e:
            logging.error(f"Error downloading file: {e}")
            return f"Error: {str(e)}"

    return "Client not connected."

@app.route('/delete_attachment/<int:message_id>', methods=['POST'])
async def delete_attachment(message_id):
    if 'logged_in' not in session:
        return redirect(url_for('index'))

    user_id = session.get('phone_number')
    client = await initialize_client(user_id)
    if client and client.is_connected():
        try:
            message = await client.get_messages('me', ids=message_id)
            if message.media:
                await client.delete_messages('me', message_id)
                return redirect(url_for('attachments'))
            else:
                return "No media found in the message."
        except Exception as e:
            logging.error(f"Error deleting attachment: {e}")
            return f"Error: {str(e)}"

    return "Client not connected."

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True)
