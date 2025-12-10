
import os
import sqlite3
from uuid import uuid4
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PIL import Image

# ---------------------- Paths & App ----------------------
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_ROOT, 'site.db')
STATIC_DIR = os.path.join(APP_ROOT, 'static')
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'uploads')

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Optional: limit upload size (10 MB)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------- DB UTILS ----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            image_filename TEXT
        );

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            designation TEXT NOT NULL,
            description TEXT NOT NULL,
            image_filename TEXT
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            mobile TEXT NOT NULL,
            city TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

# ---------------------- IMAGE UTILS ----------------------
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_and_crop_image(file_storage, target_w: int = 450, target_h: int = 350) -> str | None:
    """
    Saves an uploaded image and crops it to a specific target size (center crop).
    Returns the stored filename (string) or None if invalid or processing fails.

    - Always outputs JPEG with .jpg extension to avoid content/extension mismatch.
    - Uses a temp file for the original upload, then writes the processed final file.
    """
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        return None

    # Normalize final extension to .jpg for consistent output
    name, _ext = os.path.splitext(filename)
    final_ext = ".jpg"

    # Unique final name
    unique_name = f"{name}_{uuid4().hex}{final_ext}"
    final_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    # Save raw upload temporarily (keeps original ext only for temp write)
    tmp_name = f"{name}_{uuid4().hex}{_ext}"
    tmp_path = os.path.join(app.config['UPLOAD_FOLDER'], tmp_name)

    try:
        file_storage.save(tmp_path)

        # Open & process
        with Image.open(tmp_path) as img:
            # Convert to RGB for JPEG output
            img = img.convert('RGB')

            # Resize to fill one dimension, then center crop to target
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h

            if img_ratio > target_ratio:
                # Wider than target ratio -> match height first, scale width
                new_height = target_h
                scale = new_height / img.height
                new_width = int(img.width * scale)
            else:
                # Taller/narrower -> match width first, scale height
                new_width = target_w
                scale = new_width / img.width
                new_height = int(img.height * scale)

            img = img.resize((new_width, new_height), Image.LANCZOS)

            # Center crop to (target_w, target_h)
            left = (new_width - target_w) // 2
            top = (new_height - target_h) // 2
            right = left + target_w
            bottom = top + target_h
            img = img.crop((left, top, right, bottom))

            # Save as JPEG (quality ~90 gives a good balance)
            img.save(final_path, format='JPEG', quality=90)

    except Exception as e:
        print("Image processing error:", e)
        # Clean up temp if something fails
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return None
    else:
        # Clean up temp on success
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    return unique_name

# ---------------------- ROUTES: PUBLIC ----------------------
@app.route('/')
def index():
    conn = get_db()
    projects = conn.execute('SELECT * FROM projects ORDER BY id DESC').fetchall()
    clients = conn.execute('SELECT * FROM clients ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', projects=projects, clients=clients, title='PrimeVista')

@app.route('/contact', methods=['POST'])
def contact_submit():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    mobile = request.form.get('mobile', '').strip()
    city = request.form.get('city', '').strip()

    if not (full_name and email and mobile and city):
        flash('Please fill all contact form fields.', 'error')
        return redirect(url_for('index'))

    conn = get_db()
    conn.execute(
        'INSERT INTO contacts (full_name, email, mobile, city, created_at) VALUES (?, ?, ?, ?, ?)',
        (full_name, email, mobile, city, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    flash('Thank you! Your contact details have been submitted.', 'success')
    return redirect(url_for('index'))

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email', '').strip()
    if not email:
        flash('Please enter an email address.', 'error')
        return redirect(url_for('index'))
    conn = get_db()
    conn.execute('INSERT INTO subscriptions (email, created_at) VALUES (?, ?)', (email, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    flash('Subscribed successfully!', 'success')
    return redirect(url_for('index'))

# ---------------------- ROUTES: ADMIN ----------------------
@app.route('/admin')
def admin_dashboard():
    conn = get_db()
    counts = {
        'projects': conn.execute('SELECT COUNT(*) AS c FROM projects').fetchone()['c'],
        'clients': conn.execute('SELECT COUNT(*) AS c FROM clients').fetchone()['c'],
        'contacts': conn.execute('SELECT COUNT(*) AS c FROM contacts').fetchone()['c'],
        'subscriptions': conn.execute('SELECT COUNT(*) AS c FROM subscriptions').fetchone()['c'],
    }
    conn.close()
    return render_template('admin/dashboard.html', counts=counts, title='Admin · PrimeVista')

# Projects
@app.route('/admin/projects', methods=['GET', 'POST'])
def admin_projects():
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        image = request.files.get('image')

        filename = None
        if image and image.filename:
            # Crop to 450x350 before storing
            filename = save_and_crop_image(image, target_w=450, target_h=350)

        if not (name and description):
            flash('Please provide project name and description.', 'error')
        else:
            conn.execute(
                'INSERT INTO projects (name, description, image_filename) VALUES (?, ?, ?)',
                (name, description, filename)
            )
            conn.commit()
            flash('Project added!', 'success')

    projects = conn.execute('SELECT * FROM projects ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin/projects.html', projects=projects, title='Projects · PrimeVista')

@app.route('/admin/projects/delete/<int:pid>', methods=['POST'])
def delete_project(pid):
    conn = get_db()
    row = conn.execute('SELECT image_filename FROM projects WHERE id = ?', (pid,)).fetchone()
    if row:
        if row['image_filename']:
            path = os.path.join(app.config['UPLOAD_FOLDER'], row['image_filename'])
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print('Error deleting image:', e)
        conn.execute('DELETE FROM projects WHERE id = ?', (pid,))
        conn.commit()
        flash('Project deleted.', 'success')
    conn.close()
    return redirect(url_for('admin_projects'))

# Clients
@app.route('/admin/clients', methods=['GET', 'POST'])
def admin_clients():
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        designation = request.form.get('designation', '').strip()
        description = request.form.get('description', '').strip()
        image = request.files.get('image')

        filename = None
        if image and image.filename:
            # Crop to 450x350 before storing (you can change to 350x350 if preferred)
            filename = save_and_crop_image(image, target_w=450, target_h=350)

        if not (name and designation and description):
            flash('Please provide client name, designation and description.', 'error')
        else:
            conn.execute(
                'INSERT INTO clients (name, designation, description, image_filename) VALUES (?, ?, ?, ?)',
                (name, designation, description, filename)
            )
            conn.commit()
            flash('Client added!', 'success')

    clients = conn.execute('SELECT * FROM clients ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin/clients.html', clients=clients, title='Clients · PrimeVista')

@app.route('/admin/clients/delete/<int:cid>', methods=['POST'])
def delete_client(cid):
    conn = get_db()
    row = conn.execute('SELECT image_filename FROM clients WHERE id = ?', (cid,)).fetchone()
    if row:
        if row['image_filename']:
            path = os.path.join(app.config['UPLOAD_FOLDER'], row['image_filename'])
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print('Error deleting image:', e)
        conn.execute('DELETE FROM clients WHERE id = ?', (cid,))
        conn.commit()
        flash('Client deleted.', 'success')
    conn.close()
    return redirect(url_for('admin_clients'))

# Contacts
@app.route('/admin/contacts')
def admin_contacts():
    conn = get_db()
    contacts = conn.execute('SELECT * FROM contacts ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin/contacts.html', contacts=contacts, title='Contacts · PrimeVista')

# Subscriptions
@app.route('/admin/subscriptions')
def admin_subscriptions():
    conn = get_db()
    subs = conn.execute('SELECT * FROM subscriptions ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin/subscriptions.html', subs=subs, title='Subscriptions · PrimeVista')

# ---------------------- AUTO DB INIT ----------------------
if not os.path.exists(DB_PATH):
    print("Initializing DB...")
    init_db()

# ---------------------- LOCAL RUN ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


