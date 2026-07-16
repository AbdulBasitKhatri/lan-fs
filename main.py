import os
import socket
import sqlite3
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash, g
from jinja2 import DictLoader

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Random secret key for session management

# Configurations
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared_files')
DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files_database.db')
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

# --- HTML TEMPLATES ---

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LAN-FS</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --bg: #09090b;
            --container-bg: #121214;
            --border: #27272a;
            --text-primary: #f4f4f5;
            --text-secondary: #a1a1aa;
            --primary: #bb86fc;
            --primary-glow: rgba(187, 134, 252, 0.15);
            --accent-cyan: #03dac6;
            --accent-red: #ff7597;
            --btn-gradient: linear-gradient(135deg, #bb86fc, #7c3aed);
        }

        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text-primary);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            min-height: 100vh;
            box-sizing: border-box;
            background-image: radial-gradient(circle at 50% 0%, rgba(124, 58, 237, 0.08) 0%, transparent 60%);
        }

        .container {
            width: 100%;
            max-width: 800px;
            display: flex;
            flex-direction: column;
            gap: 25px;
        }

        header {
            text-align: center;
            margin-bottom: 10px;
        }

        h1 {
            font-size: 2.2rem;
            font-weight: 800;
            margin: 0 0 10px 0;
            background: linear-gradient(135deg, #f4f4f5 30%, #bb86fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.03em;
        }

        h2 {
            font-size: 1.3rem;
            font-weight: 700;
            margin: 0 0 20px 0;
            color: var(--primary);
            letter-spacing: -0.01em;
        }

        .card {
            background-color: var(--container-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            position: relative;
        }

        .network-info {
            background: rgba(3, 218, 198, 0.04);
            border-left: 4px solid var(--accent-cyan);
            border-radius: 8px;
            padding: 15px 20px;
            font-size: 0.95rem;
            line-height: 1.5;
            color: var(--text-secondary);
        }

        .network-info strong {
            color: var(--accent-cyan);
            font-family: 'JetBrains Mono', monospace;
        }

        .flash-messages {
            background: rgba(255, 117, 151, 0.08);
            border: 1px solid rgba(255, 117, 151, 0.2);
            color: var(--accent-red);
            border-radius: 10px;
            padding: 12px 20px;
            font-weight: 500;
            text-align: center;
            font-size: 0.9rem;
        }

        /* Forms styling */
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        @media (max-width: 600px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
        }

        .form-group {
            margin-bottom: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .form-group.full-width {
            grid-column: span 2;
        }

        @media (max-width: 600px) {
            .form-group.full-width {
                grid-column: span 1;
            }
        }

        label {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        input[type="file"] {
            border: 1px dashed var(--border);
            padding: 15px;
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-secondary);
            cursor: pointer;
            transition: border-color 0.2s;
        }

        input[type="file"]:hover {
            border-color: var(--primary);
        }

        input[type="password"], input[type="text"], input[type="number"] {
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 0.95rem;
            outline: none;
            transition: all 0.2s;
        }
        
        select {
            background-color: rgba(25, 25, 25, 1);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 0.95rem;
            outline: none;
            transition: all 0.2s;
        }

        input:focus, select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }

        /* Combined Expiry controls styling */
        .expiry-row {
            display: flex;
            gap: 10px;
        }
        .expiry-row input {
            flex: 2;
        }
        .expiry-row select {
            flex: 1;
        }

        /* Password input decoration with toggle button */
        .input-with-action {
            position: relative;
            display: flex;
            align-items: center;
        }

        .input-with-action input {
            width: 100%;
            padding-right: 45px;
        }

        .btn-toggle-view {
            position: absolute;
            right: 12px;
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1.1rem;
            padding: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s;
        }

        .btn-toggle-view:hover {
            color: var(--primary);
        }

        button[type="submit"], .btn-primary {
            background: var(--btn-gradient);
            color: #ffffff;
            border: none;
            border-radius: 10px;
            padding: 14px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.1s, opacity 0.2s;
        }

        button[type="submit"]:hover, .btn-primary:hover {
            opacity: 0.95;
            box-shadow: 0 4px 15px var(--primary-glow);
        }

        button[type="submit"]:active, .btn-primary:active {
            transform: scale(0.99);
        }

        /* Files Section */
        .file-list {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .file-card {
            background-color: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s, border-color 0.2s;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .file-card:hover {
            border-color: #3f3f46;
        }

        .file-card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
        }

        .file-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            font-size: 1.05rem;
            color: var(--text-primary);
        }

        .badge-lock {
            font-size: 0.85rem;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }

        .badge-lock.secured {
            background-color: rgba(187, 134, 252, 0.1);
            color: var(--primary);
            border: 1px solid rgba(187, 134, 252, 0.2);
        }

        .badge-lock.public {
            background-color: rgba(3, 218, 198, 0.1);
            color: var(--accent-cyan);
            border: 1px solid rgba(3, 218, 198, 0.2);
        }

        .actions {
            display: flex;
            gap: 10px;
        }

        .btn-action {
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            border: none;
            transition: all 0.2s;
        }

        .btn-action.copy {
            background-color: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-action.copy:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }

        .btn-action.download {
            background-color: var(--accent-cyan);
            color: #09090b;
        }

        .btn-action.download:hover {
            background-color: #018786;
        }

        .btn-action.delete {
            background-color: rgba(255, 117, 151, 0.1);
            color: var(--accent-red);
            border: 1px solid rgba(255, 117, 151, 0.2);
        }

        .btn-action.delete:hover {
            background-color: var(--accent-red);
            color: #09090b;
        }

        .link-row {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 8px 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: var(--accent-cyan);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid rgba(255, 255, 255, 0.02);
            word-break: break-all;
        }

        .file-metadata {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            font-size: 0.8rem;
            color: var(--text-secondary);
            border-top: 1px solid rgba(255, 255, 255, 0.04);
            padding-top: 12px;
        }

        .meta-item {
            display: flex;
            align-items: center;
            gap: 6px;
            background-color: rgba(255, 255, 255, 0.02);
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.02);
        }

        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: var(--primary);
            text-decoration: none;
            font-size: 0.95rem;
            font-weight: 600;
        }

        .back-link:hover {
            text-decoration: underline;
        }
    </style>
    
    <script>
        function togglePassword(inputId, btn) {
            const input = document.getElementById(inputId);
            if (input.type === "password") {
                input.type = "text";
                btn.textContent = "🙈";
            } else {
                input.type = "password";
                btn.textContent = "👁️";
            }
        }

        function copyToClipboard(text, btnId) {
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.getElementById(btnId);
                const originalText = btn.innerText;
                btn.innerText = "Copied! ✓";
                btn.style.borderColor = "var(--accent-cyan)";
                btn.style.color = "var(--accent-cyan)";
                setTimeout(() => {
                    btn.innerText = originalText;
                    btn.style.borderColor = "var(--border)";
                    btn.style.color = "var(--text-primary)";
                }, 2000);
            });
        }
    </script>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔒 LAN-FS </h1>
            <div class="network-info">
                Active Storage Gateway: <strong>http://{{ ip_address }}:5000</strong><br>
                <span>Instantly share files protected with custom rules with anyone on your local network.</span>
            </div>
        </header>

        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="flash-messages">
              {% for message in messages %}
                <p>{{ message }}</p>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

INDEX_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<div class="card">
    <h2>📤 Upload New File</h2>
    <form action="{{ url_for('upload_file') }}" method="post" enctype="multipart/form-data">
        <div class="form-group">
            <label for="file">Select File</label>
            <input type="file" name="file" id="file" required>
        </div>
        
        <div class="form-grid">
            <div class="form-group">
                <label for="password">Access Password (Optional)</label>
                <div class="input-with-action">
                    <input type="password" name="password" id="password" placeholder="Leave blank for public download">
                    <button type="button" class="btn-toggle-view" onclick="togglePassword('password', this)">👁️</button>
                </div>
            </div>
            
            <div class="form-group">
                <label for="delete_secret">Secret Deletion Key (Required)</label>
                <div class="input-with-action">
                    <input type="password" name="delete_secret" id="delete_secret" placeholder="Required to delete file later" required>
                    <button type="button" class="btn-toggle-view" onclick="togglePassword('delete_secret', this)">👁️</button>
                </div>
            </div>

            <div class="form-group">
                <label for="max_downloads">Max Downloads Limit (Optional)</label>
                <input type="number" name="max_downloads" id="max_downloads" min="1" placeholder="Unlimited downloads">
            </div>

            <div class="form-group">
                <label for="expiry_value">Custom Life Span</label>
                <div class="expiry-row">
                    <input type="number" name="expiry_value" id="expiry_value" min="0" value="30" required placeholder="Duration value">
                    <select name="expiry_unit" id="expiry_unit">
                        <option value="seconds">Seconds</option>
                        <option value="minutes" selected>Minutes</option>
                        <option value="hours">Hours</option>
                        <option value="days">Days</option>
                        <option value="never">Never Expire</option>
                    </select>
                </div>
            </div>
        </div>
        
        <button type="submit" style="margin-top: 10px; width: 100%;">Upload & Lock Securely</button>
    </form>
</div>

<div class="card">
    <h2>📁 Active Storage Repository</h2>
    <div class="file-list">
        {% if files %}
            {% for file in files %}
                {% set share_url = "http://" ~ ip_address ~ ":5000" ~ url_for('request_download', file_id=file.id) %}
                <div class="file-card">
                    <div class="file-card-top">
                        <div class="file-title">
                            {% if file.password_hash %}
                                <span class="badge-lock secured">🔒 Locked</span>
                            {% else %}
                                <span class="badge-lock public">🔓 Open</span>
                            {% endif %}
                            <span>{{ file.original_name }}</span>
                        </div>
                        <div class="actions">
                            <button id="copy-btn-{{ file.id }}" class="btn-action copy" onclick="copyToClipboard('{{ share_url }}', 'copy-btn-{{ file.id }}')">Copy Link</button>
                            <a href="{{ url_for('request_download', file_id=file.id) }}" class="btn-action download">Download</a>
                            <a href="{{ url_for('delete_request', file_id=file.id) }}" class="btn-action delete">Delete</a>
                        </div>
                    </div>
                    
                    <div class="link-row">
                        <span>{{ share_url }}</span>
                    </div>

                    <div class="file-metadata">
                        <span class="meta-item">🕒 Uploaded: {{ file.upload_time }}</span>
                        <span class="meta-item">📥 Downloads: {{ file.download_count }}{% if file.max_downloads %}/{{ file.max_downloads }}{% endif %}</span>
                        <span class="meta-item">⌛ Expiry: {% if file.expire_time %}{{ file.expire_time }}{% else %}Never{% endif %}</span>
                    </div>
                </div>
            {% endfor %}
        {% else %}
            <p style="text-align: center; color: var(--text-secondary); margin: 20px 0;">No active files uploaded to this storage gateway yet.</p>
        {% endif %}
    </div>
</div>

<script>
    // Disable input if "Never Expire" is chosen
    const expiryUnit = document.getElementById('expiry_unit');
    const expiryValue = document.getElementById('expiry_value');
    expiryUnit.addEventListener('change', function() {
        if (this.value === 'never') {
            expiryValue.disabled = true;
            expiryValue.required = false;
            expiryValue.value = '';
        } else {
            expiryValue.disabled = false;
            expiryValue.required = true;
            if (!expiryValue.value) expiryValue.value = '30';
        }
    });
</script>
{% endblock %}
"""

UNLOCK_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 500px; margin: 40px auto; text-align: center;">
    <h2>🔑 Decrypt File</h2>
    <p style="color: var(--text-secondary); margin-bottom: 25px;">Enter the shared vault key to proceed with downloading:<br><strong style="color: var(--primary);">{{ original_name }}</strong></p>
    
    <form action="{{ url_for('verify_and_download', file_id=file_id) }}" method="post" style="text-align: left;">
        <div class="form-group">
            <label for="password">Vault Key Password</label>
            <div class="input-with-action">
                <input type="password" name="password" id="password" required autofocus placeholder="Enter password key">
                <button type="button" class="btn-toggle-view" onclick="togglePassword('password', this)">👁</button>
            </div>
        </div>
        <button type="submit" style="width: 100%; margin-top: 10px;">Unlock & Stream File</button>
    </form>
    
    <a href="{{ url_for('index') }}" class="back-link">← Cancel and Back</a>
</div>
{% endblock %}
"""

DELETE_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<div class="card" style="max-width: 500px; margin: 40px auto; text-align: center;">
    <h2 style="color: var(--accent-red);">🗑️ Destructive Action</h2>
    <p style="color: var(--text-secondary); margin-bottom: 25px;">Provide the matching secret key to permanently wipe <strong style="color: var(--accent-red);">{{ original_name }}</strong> from local server storage.</p>
    
    <form action="{{ url_for('delete_confirm', file_id=file_id) }}" method="post" style="text-align: left;">
        <div class="form-group">
            <label for="delete_secret">Secret Deletion Key</label>
            <div class="input-with-action">
                <input type="password" name="delete_secret" id="delete_secret" required autofocus placeholder="Enter your secret key">
                <button type="button" class="btn-toggle-view" onclick="togglePassword('delete_secret', this)">👁</button>
            </div>
        </div>
        <button type="submit" class="btn-primary" style="background: var(--accent-red); color: #09090b; width: 100%; margin-top: 10px;">Confirm Permanent Destruction</button>
    </form>
    
    <a href="{{ url_for('index') }}" class="back-link" style="color: var(--text-secondary);">← Keep File and Return</a>
</div>
{% endblock %}
"""

app.jinja_loader = DictLoader({
    'base.html': BASE_TEMPLATE,
    'index.html': INDEX_TEMPLATE,
    'unlock.html': UNLOCK_TEMPLATE,
    'delete.html': DELETE_TEMPLATE
})

# --- UTILITIES ---

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

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
    return render_template('index.html', ip_address=get_local_ip(), files=files)

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
        
        # Custom expiration duration parser (0 seconds to N days)
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
        ip_address=get_local_ip(), 
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
    return render_template('delete.html', ip_address=get_local_ip(), file_id=file_id, original_name=row['original_name'])

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
    print(f"\n" + "="*50)
    print(f"🚀 SERVER LIVE ON YOUR LOCAL NETWORK!")
    print(f"👉 Access URL: http://{local_ip}:5000")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)