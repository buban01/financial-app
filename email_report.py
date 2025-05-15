import mysql.connector
import config
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from email.mime.multipart import MIMEMultipart

def send_email(to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = config.SMTP_USER
    msg['To'] = to_email

    # Attach the HTML body
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
            print(f"[EMAIL] Sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")

def get_client_portfolios():
    conn = mysql.connector.connect(
        host=config.DB_HOST, user=config.DB_USER,
        password=config.DB_PASS, database=config.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients")
    clients = cursor.fetchall()
    portfolios = []

    for client in clients:
        cursor.execute("""
            SELECT f.name AS fund_name, i.units, i.current_nav
            FROM investments i
            JOIN funds f ON i.fund_id = f.id
            WHERE i.client_id = %s
        """, (client['id'],))
        investments = cursor.fetchall()
        portfolios.append((client, investments))

    cursor.close()
    conn.close()
    return portfolios

def format_portfolio_html(client, investments):
    total = 0.0
    rows = ""

    for inv in investments:
        value = inv['units'] * inv['current_nav']
        total += value
        rows += f"""
        <tr>
            <td>{inv['fund_name']}</td>
            <td>{inv['units']}</td>
            <td>₹{inv['current_nav']}</td>
            <td>₹{value:.2f}</td>
        </tr>
        """

    return f"""
    <html>
    <body>
        <h2>Portfolio for {client['name']}</h2>
        <p><strong>Email:</strong> {client['email']}<br>
        <strong>Phone:</strong> {client['phone']}</p>

        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif;">
            <thead style="background-color: #f2f2f2;">
                <tr>
                    <th>Fund Name</th>
                    <th>Units</th>
                    <th>Current NAV</th>
                    <th>Total Value</th>
                </tr>
            </thead>
            <tbody>
                {rows}
                <tr style="font-weight: bold; background-color: #e8e8e8;">
                    <td colspan="3">Total Portfolio Value</td>
                    <td>₹{total:.2f}</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """


def send_daily_summaries():
    print("[EMAIL] Sending daily summaries...")
    for client, investments in get_client_portfolios():
        html = format_portfolio_html(client, investments)
        send_email(client['email'], f"📈 Daily Portfolio Update - {datetime.today().strftime('%d-%b-%Y')}", html)

def send_monthly_reports():
    print("[EMAIL] Sending monthly reports...")
    for client, investments in get_client_portfolios():
        html = format_portfolio_html(client, investments)
        send_email(client['email'], f"📅 Monthly Portfolio Report - {datetime.today().strftime('%B %Y')}", html)
