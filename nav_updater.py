import requests
import config
import mysql.connector
from datetime import datetime

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

def update_all_navs():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(AMFI_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        print("[NAV Update] NAV data fetched successfully from AMFI.")
    except requests.exceptions.RequestException as e:
        print("[NAV Update] Failed to fetch NAV data:", e)
        return

    all_lines = resp.text.splitlines()
    data_lines = []

    for line in all_lines:
        parts = line.split(';')
        if len(parts) >= 6 and parts[0].strip().isdigit():
            data_lines.append(parts)

    print(f"[DEBUG] Total valid NAV lines: {len(data_lines)}")
    print("[DEBUG] Sample lines:")
    for p in data_lines[:5]:
        print(f"{p[3]} -> ₹{p[4]}")

    if not data_lines:
        print("[NAV Update] No valid NAV entries found.")
        return

    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASS,
        database=config.DB_NAME
    )
    cursor = conn.cursor()
    updated_count = 0

    for parts in data_lines:
        try:
            scheme_name = parts[3].strip()
            nav_val = float(parts[4])
            nav_date = datetime.strptime(parts[5].strip(), "%d-%b-%Y").date()

            cursor.execute("""
                UPDATE investments i
                JOIN funds f ON i.fund_id = f.id
                SET i.current_nav = %s, i.last_updated = %s
                WHERE LOWER(f.name) LIKE LOWER(%s)
            """, (nav_val, nav_date, f"%{scheme_name}%"))

            print(f"[SQL Update] Updating: {scheme_name} | NAV: ₹{nav_val} | Rows affected: {cursor.rowcount}")
            updated_count += cursor.rowcount
        except Exception as e:
            print(f"[ERROR] Failed to process line: {parts} | Error: {e}")
            continue

    conn.commit()
    cursor.close()
    conn.close()

    print(f"[NAV Update] NAVs updated for {updated_count} investments.")
