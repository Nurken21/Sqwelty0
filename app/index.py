from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import io
from werkzeug.utils import secure_filename
import csv

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

def init_sqlite_db():
    conn = sqlite3.connect('users_db/users.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id INTEGER PRIMARY KEY, 
                     full_name TEXT, 
                     email TEXT UNIQUE, 
                     password TEXT, 
                     role TEXT,
                     banned INTEGER DEFAULT 0,  
                     ban_reason TEXT,
                     disabled INTEGER DEFAULT 0,
                     disable_reason TEXT)''')
    conn.close()

def init_admin_sqlite_db():
    database_path = os.path.join(app.root_path, 'templates/admin/admin_panel/admin_db/admins.db')
    conn = sqlite3.connect(database_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS admins (
                        id INTEGER PRIMARY KEY, 
                        username TEXT, 
                        email TEXT, 
                        password TEXT,
                        confkey TEXT
                    )''')
    conn.close()

def init_flights_table():
    conn = sqlite3.connect('templates/admin/admin_panel/flights_db/flights.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS flights (
                        id INTEGER PRIMARY KEY,
                        flight_number TEXT,
                        departure TEXT,
                        destination TEXT,
                        departure_time TEXT,
                        arrival_time TEXT,
                        price INTEGER
                    )''')
    
    # Check if the 'price' column exists, if not, add it
    cursor.execute('''PRAGMA table_info(flights)''')
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    if 'price' not in column_names:
        cursor.execute('''ALTER TABLE flights ADD COLUMN price INTEGER''')

    conn.close()

def get_flights_from_database():
    conn = sqlite3.connect('templates/admin/admin_panel/flights_db/flights.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM flights')
    flights = cursor.fetchall()
    conn.close()
    return flights

def init_payment_sqlite_db():
    conn = sqlite3.connect('templates/admin/admin_panel/payment/payment_db.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS payments 
                    (id INTEGER PRIMARY KEY, 
                     card_number TEXT, 
                     expiry_date TEXT,
                     cvv TEXT)''')
    conn.close()

@app.route('/')
def home():
    flights = get_flights_from_database()
    if 'email' in session:
        email = session['email']
        return render_template('site/index.html', email=email, flights=flights)
    return render_template('site/index.html', flights=flights)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'email' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('users_db/users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            if user[3] == password:
                session['email'] = email
                return redirect(url_for('home'))
            else:
                flash('Неверный пароль. Пожалуйста, попробуйте еще раз.')
        else:
            flash('Пользователь с таким email не найден. Пожалуйста, зарегистрируйтесь.')

    return render_template('users/users.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']  
        role = request.form['role']

        conn = sqlite3.connect('users_db/users.db')
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            flash('Пользователь с таким email уже существует.')
        else:
            cursor.execute('INSERT INTO users (full_name, email, password, role) VALUES (?, ?, ?, ?)',
                           (full_name, email, password, role))
            conn.commit()
            conn.close()
            flash('Регистрация прошла успешно. Войдите, используя свои учетные данные.')
            return redirect(url_for('login'))

    return render_template('users/users_regis/users_regis.html')

@app.route('/admin_auth', methods=['GET', 'POST'])
def admin_auth():
    if 'authenticated_admin' in session:
        return redirect(url_for('admin_panel'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        code = request.form['code']

        conn = sqlite3.connect('templates/admin/admin_panel/admin_db/admins.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admins WHERE username = ? AND password = ? AND email = ? AND confkey = ?',
                       (username, password, email, code))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session['authenticated_admin'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Неверные данные аутентификации администратора!')

    return render_template('admin/auth_admin.html')

@app.route('/admin_panel')
def admin_panel():
    if 'authenticated_admin' not in session:
        return redirect(url_for('admin_auth'))

    users = query_database('SELECT * FROM users')
    flights = get_flights_from_database()

    if 'email' in session:
        email = session['email']
        return render_template('admin/admin_panel/admin_panel.html', email=email, users=users, flights=flights)
    else:
        return render_template('admin/admin_panel/admin_panel.html', users=users, flights=flights)

def query_database(query):
    conn = sqlite3.connect('users_db/users.db')
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        reason_disable = request.form.get('reason_disable', '')
        action = request.form.get('action')

        conn = sqlite3.connect('users_db/users.db')
        cursor = conn.cursor()

        if action == 'save':
            cursor.execute('UPDATE users SET full_name=?, email=?, password=?, role=? WHERE id=?',
                           (full_name, email, password, role, user_id))
            flash('User data successfully updated!')
        elif action == 'ban':
            cursor.execute('UPDATE users SET banned=?, ban_reason=? WHERE id=?',
                           (1, reason_disable, user_id))
            flash('User has been banned!')
        elif action == 'disable':
            cursor.execute('UPDATE users SET disabled=?, disable_reason=? WHERE id=?',
                           (1, reason_disable, user_id))
            flash('User has been disabled!')

        conn.commit()
        conn.close()

        return redirect(url_for('admin_panel'))
    else:
        conn = sqlite3.connect('users_db/users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))
        user = cursor.fetchone()
        conn.close()

        return render_template('admin/admin_panel/edit_user.html', user=user, user_id=user_id)

@app.route('/edit_flight/<int:flight_id>', methods=['GET', 'POST'])
def edit_flight(flight_id):
    if request.method == 'POST':
        conn = sqlite3.connect('templates/admin/admin_panel/flights_db/flights.db')
        cursor = conn.cursor()

        if 'destination' in request.form and 'departure_time' in request.form and 'arrival_time' in request.form and 'price' in request.form:
            destination = request.form['destination']
            departure_time = request.form['departure_time']
            arrival_time = request.form['arrival_time']
            price = request.form['price']

            cursor.execute('UPDATE flights SET destination=?, departure_time=?, arrival_time=?, price=? WHERE id=?',
                           (destination, departure_time, arrival_time, price, flight_id))

            conn.commit()
            conn.close()

            flash('Flight data successfully updated!')
            return redirect(url_for('admin_panel'))
        else:
            flash('Failed to update flight data. Please make sure all fields are filled.')

    conn = sqlite3.connect('templates/admin/admin_panel/flights_db/flights.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM flights WHERE id=?', (flight_id,))
    flight = cursor.fetchone()
    conn.close()

    return render_template('admin/admin_panel/edit_flight.html', flight=flight, flight_id=flight_id)

@app.route('/delete_flight/<int:flight_id>', methods=['POST'])
def delete_flight(flight_id):
    if request.method == 'POST':
        flash('Flight successfully deleted!')
        return redirect(url_for('admin_panel'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if request.method == 'POST':
        conn = sqlite3.connect('users_db/users.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return redirect('/')

@app.route('/upload_data', methods=['POST'])
def upload_data():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!')
            return redirect(url_for('admin_panel'))
        if file:
            filename = secure_filename(file.filename)
            if filename.endswith('.csv'):
                conn = sqlite3.connect('users_db/users.db')
                cursor = conn.cursor()
                
                with io.TextIOWrapper(file.stream, encoding='utf-8') as csvfile:
                    csvreader = csv.reader(csvfile)
                    next(csvreader, None)
                    for row in csvreader:
                        if len(row) == 8:
                            cursor.execute("INSERT INTO users (full_name, email, password, role) VALUES (?, ?, ?, ?)",
                                           (row[0], row[1], row[2], row[3]))
                        else:
                            flash('Invalid data format! Each row should contain 8 values.')
                            return redirect(url_for('admin_panel'))
                conn.commit()
                conn.close()

                flash('Data uploaded successfully!')
                return redirect(url_for('admin_panel'))
            else:
                flash('Invalid file format! Please upload a CSV file.')
                return redirect(url_for('admin_panel'))
            
@app.route('/admin_logout')
def admin_logout():
    session.pop('authenticated_admin', None)
    flash('You have successfully logged out of the admin panel.')
    return redirect(url_for('admin_auth'))

@app.route('/add_flight', methods=['GET', 'POST'])
def add_flight():
    if request.method == 'POST':
        try:
            flight_number = request.form['flight_number']
            departure = request.form['departure']
            destination = request.form['destination']
            departure_time = request.form['departure_time']
            arrival_time = request.form['arrival_time']
            price = request.form['price']

            if flight_number and departure and destination and departure_time and arrival_time and price:
                conn = sqlite3.connect('templates/admin/admin_panel/flights_db/flights.db')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO flights (flight_number, departure, destination, departure_time, arrival_time, price) VALUES (?, ?, ?, ?, ?, ?)',
                               (flight_number, departure, destination, departure_time, arrival_time, price))
                conn.commit()
                conn.close()
                flash('Flight successfully added!')
                return redirect(url_for('add_flight'))
            else:
                flash('Insufficient data to add a flight! Please fill in all fields.')
                return redirect(url_for('add_flight'))
        except KeyError:
            flash('Error processing form data!')
            return redirect(url_for('add_flight'))
    else:
        return render_template('admin/admin_panel/add_flight.html')

@app.route('/buy_ticket', methods=['GET', 'POST'])
def buy_ticket():
    if request.method == 'POST':
        if 'email' not in session:
            flash('Please login to buy a ticket.')
            return redirect(url_for('login'))
        
        flight_id = request.form.get('flight_id')
        if not flight_id:
            flash('Please select a flight to proceed.')
            return redirect(url_for('home'))

        return redirect(url_for('payment', flight_id=flight_id))
    
    else:
        flash('Invalid request method.')
        return redirect(url_for('home'))

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        flash('Payment successfully processed. Ticket successfully purchased!')
        return redirect(url_for('home'))
    else:
        flight_id = request.args.get('flight_id')
        if not flight_id:
            flash('Failed to get flight data. Please select a flight again.')
            return redirect(url_for('home'))
        
        return render_template('site/score.html', flight_id=flight_id)
    
@app.route('/process_payment', methods=['POST'])
def process_payment():
    if request.method == 'POST':
        card_number = request.form['card_number']
        expiry_date = request.form['expiry_date']
        cvv = request.form['cvv']

        conn = sqlite3.connect('templates/admin/admin_panel/payment/payment_db.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO payments (card_number, expiry_date, cvv) VALUES (?, ?, ?)",
                       (card_number, expiry_date, cvv))
        conn.commit()
        conn.close()

        flash('Payment successfully processed and card data saved!')
        return redirect(url_for('home'))
    

if __name__ == '__main__':
    init_sqlite_db()
    init_admin_sqlite_db()
    init_flights_table()
    init_payment_sqlite_db()
    app.run(host='0.0.0.0', debug=True)
