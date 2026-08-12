import os
import socket
import sqlite3
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash, g

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Random secret key for session management

# Configurations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'shared_files')
DATABASE_FILE = os.path.join(BASE_DIR, 'files_database.db')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Max size: 500MB

# --- DATABASE SETUP ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_FILE)
        db.row_factory = sqlite3.Row
        # Force table check and creation every time a connection is opened
        create_tables_safe(db)
    return db

def create_tables_safe(db_conn):
    """Ensures tables are built inside the active database connection context."""
    db_conn.execute("""
        CREATE TABLE IF NOT EXISTS shared_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            password_hash TEXT,
            delete_secret_hash TEXT NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            download_count INTEGER DEFAULT 0,
            max_downloads INTEGER,
            expire_time TIMESTAMP
        )
    """)
    db_conn.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- UTILITIES ---

def get_local_ip():
    """
    Attempts to get the local LAN IP address when running locally.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_base_url():
    """
    Dynamically returns the complete base URL (domain or IP).
    - If hosted on a cloud server (like PythonAnywhere), it returns 'https://domain.com' or 'http://domain.com'.
    - If running locally, it falls back to your Wi-Fi LAN IP (e.g., 'http://192.168.1.50:5000').
    """
    if request:
        host = request.host  # Captures 'username.pythonanywhere.com' or '192.168.x.x:5000'
        protocol = "https" if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https' else "http"
        return f"{protocol}://{host}"
    
    local_ip = get_local_ip()
    return f"http://{local_ip}:5000"

def purge_expired_files():
    db = get_db()
    now = datetime.now()
    
    # Check physical records past their calculated lifetime limits
    expired_by_time = db.execute(
        "SELECT * FROM shared_files WHERE expire_time IS NOT NULL AND expire_time < ?",
        (now.strftime('%Y-%m-%d %H:%M:%S'),)
    ).fetchall()
    
    # Check records exceeding download restrictions
    expired_by_limit = db.execute(
        "SELECT * FROM shared_files WHERE max_downloads IS NOT NULL AND download_count >= max_downloads"
    ).fetchall()
    
    all_expired = list(expired_by_time) + list(expired_by_limit)
    
    for row in all_expired:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], row['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.execute("DELETE FROM shared_files WHERE id = ?", (row['id'],))
    db.commit()

# --- ROUTING LOGIC ---

@app.route('/')
def index():
    purge_expired_files()
    db = get_db()
    files = db.execute("SELECT * FROM shared_files ORDER BY upload_time DESC").fetchall()
    return render_template('index.html', base_url=get_base_url(), files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or not request.form.get('delete_secret'):
        flash("File or Deletion Secret key not specified!")
        return redirect(url_for('index'))
    
    file = request.files['file']
    password = request.form.get('password')
    delete_secret = request.form.get('delete_secret')
    max_downloads = request.form.get('max_downloads')
    
    expiry_value = request.form.get('expiry_value')
    expiry_unit = request.form.get('expiry_unit', 'minutes')
    
    if file.filename == '':
        flash("No file was selected.")
        return redirect(url_for('index'))
    
    if file:
        orig_name = file.filename
        secured_name = secure_filename(orig_name)
        
        # Collision resolution
        base, extension = os.path.splitext(secured_name)
        counter = 1
        while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], secured_name)):
            secured_name = f"{base}_{counter}{extension}"
            counter += 1
            
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], secured_name))
        
        pwd_hash = generate_password_hash(password) if password else None
        del_hash = generate_password_hash(delete_secret)
        
        # Custom expiration duration parser
        upload_time = datetime.now()
        expire_time = None
        
        if expiry_unit != 'never' and expiry_value is not None:
            val = int(expiry_value)
            if expiry_unit == 'seconds':
                delta = timedelta(seconds=val)
            elif expiry_unit == 'minutes':
                delta = timedelta(minutes=val)
            elif expiry_unit == 'hours':
                delta = timedelta(hours=val)
            elif expiry_unit == 'days':
                delta = timedelta(days=val)
                
            expire_time = (upload_time + delta).strftime('%Y-%m-%d %H:%M:%S')
            
        max_dl = int(max_downloads) if (max_downloads and int(max_downloads) > 0) else None
        
        db = get_db()
        db.execute("""
            INSERT INTO shared_files (filename, original_name, password_hash, delete_secret_hash, upload_time, max_downloads, expire_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (secured_name, orig_name, pwd_hash, del_hash, upload_time.strftime('%Y-%m-%d %H:%M:%S'), max_dl, expire_time))
        db.commit()
        
        flash(f"Uploaded and protected '{orig_name}' successfully!")
        return redirect(url_for('index'))

@app.route('/download-request/<int:file_id>')
def request_download(file_id):
    purge_expired_files()
    db = get_db()
    row = db.execute("SELECT * FROM shared_files WHERE id = ?", (file_id,)).fetchone()
    
    if not row:
        flash("Selected file was not found (it may have expired).")
        return redirect(url_for('index'))
        
    # Public bypass
    if not row['password_hash']:
        return serve_file_payload(row)
        
    return render_template(
        'unlock.html', 
        base_url=get_base_url(), 
        file_id=file_id, 
        original_name=row['original_name']
    )

@app.route('/download/<int:file_id>', methods=['POST'])
def verify_and_download(file_id):
    purge_expired_files()
    db = get_db()
    row = db.execute("SELECT * FROM shared_files WHERE id = ?", (file_id,)).fetchone()
    
    if not row:
        flash("Selected file was not found (it may have expired).")
        return redirect(url_for('index'))
        
    password = request.form.get('password')
    
    if row['password_hash'] and check_password_hash(row['password_hash'], password):
        return serve_file_payload(row)
    else:
        flash("Invalid Password Key.")
        return redirect(url_for('request_download', file_id=file_id))

def serve_file_payload(row):
    db = get_db()
    new_count = row['download_count'] + 1
    
    db.execute("UPDATE shared_files SET download_count = ? WHERE id = ?", (new_count, row['id']))
    db.commit()
    
    response = send_from_directory(
        app.config['UPLOAD_FOLDER'], 
        row['filename'], 
        as_attachment=True, 
        download_name=row['original_name']
    )
    
    if row['max_downloads'] and new_count >= row['max_downloads']:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], row['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.execute("DELETE FROM shared_files WHERE id = ?", (row['id'],))
        db.commit()
        
    return response

# --- DELETION LOGIC ---

@app.route('/delete-request/<int:file_id>')
def delete_request(file_id):
    db = get_db()
    row = db.execute("SELECT * FROM shared_files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        flash("File already deleted or expired.")
        return redirect(url_for('index'))
    return render_template('delete.html', base_url=get_base_url(), file_id=file_id, original_name=row['original_name'])

@app.route('/delete-confirm/<int:file_id>', methods=['POST'])
def delete_confirm(file_id):
    db = get_db()
    row = db.execute("SELECT * FROM shared_files WHERE id = ?", (file_id,)).fetchone()
    
    if not row:
        flash("Target record was not found.")
        return redirect(url_for('index'))
        
    secret = request.form.get('delete_secret')
    if check_password_hash(row['delete_secret_hash'], secret):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], row['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.execute("DELETE FROM shared_files WHERE id = ?", (file_id,))
        db.commit()
        flash(f"Destruction complete: '{row['original_name']}' is gone.")
        return redirect(url_for('index'))
    else:
        flash("Failed: Secret Deletion Key mismatch.")
        return redirect(url_for('delete_request', file_id=file_id))

if __name__ == '__main__':
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print("🚀 SERVER LIVE!")
    print(f"👉 Local Access URL: http://localhost:5000")
    print(f"👉 LAN Access URL: http://{local_ip}:5000")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)