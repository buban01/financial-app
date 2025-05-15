from flask import Flask, render_template, request, redirect, url_for, flash, session
import numpy_financial as npf
import mysql.connector
from scheduler import start_scheduler
import config
from datetime import datetime
import numpy as np


app = Flask(__name__)
app.secret_key = config.SECRET_KEY

def get_db_connection():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASS,
        database=config.DB_NAME
    )
def calculate_xirr(cash_flows):
    try:
        #amounts = [cf for _, cf in cash_flows]
        if not cash_flows:
            return None
        amounts = [cf for _, cf in cash_flows]
        if all(a == 0 for a in amounts):
            return None
        return round(npf.irr(amounts) * 100, 2)
    except Exception as e:
        print(f"[XIRR ERROR] {e}")
        return None
# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (uname, pwd))
        user = cursor.fetchone()
        cursor.close(); conn.close()
        if user:
            session['admin_logged_in'] = True
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash("You have been logged out", "info")
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
     if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
     
     client = None
     investments = []
     if request.method == 'POST':
        pan = request.form['pan'].strip().upper()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clients WHERE pan=%s", (pan,))
        client = cursor.fetchone()
        if client:
            cursor.execute("""SELECT i.id, i.units, i.purchase_nav, i.current_nav, f.name AS fund_name,
                         (SELECT txn_date FROM transactions t
                           WHERE t.investment_id = i.id
                           ORDER BY txn_date ASC LIMIT 1) AS txn_date       
                FROM investments i
                JOIN funds f ON i.fund_id=f.id
                WHERE i.client_id=%s
            """, (client['id'],))
            investments = cursor.fetchall()
        for inv in investments:
            try:
                cursor.execute("SELECT amount, txn_date FROM transactions WHERE investment_id = %s", (inv['id'],))
                txns = cursor.fetchall()
                cash_flows = []
                for t in txns:
                        try:

                          cash_flows = [(t['txn_date'], t['amount'])]
                        except Exception as e:
                            print(f"[PARSE ERROR] Transaction skipped: {t} - {e}")  

                # Add current value as final inflow
                current_value = inv['units'] * inv['current_nav']
                cash_flows.append((datetime.today().date(), current_value))

                inv['xirr'] = calculate_xirr(cash_flows)
            except Exception as e:
                    print(f"[XIRR FAIL] inv_id={inv['id']} - {e}")
                    inv['xirr'] = None
                    #investments.append(inv)
        else:
            flash(f"No client found with PAN {pan}", "warning")
        cursor.close()
        conn.close()
     return render_template('index.html', client=client, investments=investments)

from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function 

# Admin: Clients
@app.route('/admin/clients')
@login_required
def list_clients():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients")
    clients = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('clients.html', clients=clients)

@app.route('/admin/clients/add', methods=['GET', 'POST'])
@login_required
def add_client():
    if request.method == 'POST':
        pan = request.form['pan'].strip().upper()
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clients (pan, name, email, phone) VALUES (%s, %s, %s, %s)",
                       (pan, name, email, phone))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('list_clients'))
    return render_template('add_client.html')

@app.route('/admin/clients/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_client(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients WHERE id=%s", (id,))
    client = cursor.fetchone()
    if request.method == 'POST':
        pan = request.form['pan'].strip().upper()
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        cursor.execute("UPDATE clients SET pan=%s, name=%s, email=%s, phone=%s WHERE id=%s",
                       (pan, name, email, phone, id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('list_clients'))
    cursor.close()
    conn.close()
    return render_template('edit_client.html', client=client)

@app.route('/admin/clients/delete/<int:id>')
@login_required
def delete_client(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('list_clients'))

# Admin: Investments
@app.route('/admin/investments')
@login_required
def list_investments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT i.id, c.name AS client_name, f.name AS fund_name,
                             i.units, i.purchase_nav, i.current_nav, i.last_updated
                      FROM investments i
                      JOIN clients c ON i.client_id=c.id
                      JOIN funds f ON i.fund_id=f.id""")
    investments = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('investments.html', investments=investments)

@app.route('/admin/investments/add', methods=['GET', 'POST'])
@login_required
def add_investment():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients")
    clients = cursor.fetchall()
    cursor.execute("SELECT * FROM funds")
    funds = cursor.fetchall()
    if request.method == 'POST':
        client_id = request.form['client_id']
        fund_id = request.form['fund_id']
        units = float(request.form['units'])
        purchase_nav = float(request.form['purchase_nav'])
        txn_date = request.form['txn_date']
        cursor.execute("""INSERT INTO investments
                         (client_id, fund_id, units, purchase_nav, current_nav, last_updated)
                         VALUES (%s, %s, %s, %s, %s, CURDATE())""", 
                       (client_id, fund_id, units, purchase_nav, purchase_nav))
        inv_id = cursor.lastrowid
        amount = - (units * purchase_nav)
        cursor.execute("INSERT INTO transactions (investment_id, amount, txn_date) VALUES (%s, %s, %s)",
                       (inv_id, amount, txn_date))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('list_investments'))
    cursor.close()
    conn.close()
    return render_template('add_investment.html', clients=clients, funds=funds)

@app.route('/admin/investments/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_investment(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM investments WHERE id=%s", (id,))
    inv = cursor.fetchone()
    cursor.execute("SELECT * FROM clients"); clients = cursor.fetchall()
    cursor.execute("SELECT * FROM funds"); funds = cursor.fetchall()
    if request.method == 'POST':
        client_id = request.form['client_id']
        fund_id = request.form['fund_id']
        units = request.form['units']
        purchase_nav = request.form['purchase_nav']
        cursor.execute("""UPDATE investments
                         SET client_id=%s, fund_id=%s, units=%s, purchase_nav=%s
                         WHERE id=%s""", 
                       (client_id, fund_id, units, purchase_nav, id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('list_investments'))
    cursor.close()
    conn.close()
    return render_template('edit_investment.html', inv=inv, clients=clients, funds=funds)

@app.route('/admin/investments/delete/<int:id>')
@login_required
def delete_investment(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE investment_id = %s", (id,))
    cursor.execute("DELETE FROM investments WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('list_investments'))

@app.route('/admin/funds/add', methods=['GET', 'POST'])
@login_required
def add_fund():
    if request.method == 'POST':
        name = request.form['name'].strip()
        fund_type = request.form['type']
        #scheme_code = request.form['scheme_code'].strip()
        #isin = request.form.get('isin', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            print(f"[DEBUG] Inserting fund: {name}, {fund_type}")
            cursor.execute(
                "INSERT INTO funds (name, type) VALUES (%s, %s)",
                (name, fund_type)
            )
            conn.commit()
            flash("Fund added successfully!", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            print(f"[ERROR] {err}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('add_fund'))

    return render_template('add_fund.html')


if __name__ == '__main__':
    # Start scheduler
    start_scheduler()
    app.run(host='0.0.0.0', port=5000)
