from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import time
from selenium.webdriver.support.ui import WebDriverWait
import selenium.common.exceptions
from selenium.webdriver.support import expected_conditions as EC
import os
from datetime import datetime
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--headless")  # Run in headless mode
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("--window-size=1920,1080")  # Ensure all rows are rendered
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

driver.get("https://stockanalysis.com/stocks/screener/")
# Wait for the table to load instead of fixed sleep
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
)

# Try to close cookie/consent overlay if present, but do not print stacktrace
try:
    overlays = driver.find_elements(By.CLASS_NAME, "fc-dialog-overlay")
    if overlays:
        buttons = driver.find_elements(By.XPATH, "//button[contains(translate(., 'ACEPT', 'acept'), 'accept') or contains(translate(., 'AGREE', 'agree'), 'agree') or contains(., 'I agree') or contains(., 'OK')]")
        if buttons:
            buttons[0].click()
            time.sleep(0.5)  # Reduced sleep for stability
        else:
            print("Overlay detected but no close/accept button found.")
except selenium.common.exceptions.NoSuchElementException:
    pass
except Exception:
    print("Could not close overlay, proceeding anyway.")

def get_table_data():
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    data = []
    for row in rows:
        cells = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]
        data.append(cells)
    return data

seen_symbols = set()
all_rows = []
headers = []
page = 1

def handle_consent_popup():
    try:
        consent_btn = driver.find_element(
            By.XPATH,
            "//button[contains(translate(., 'CONSENTACCEPTAGREEOK', 'consentacceptagreeok'), 'consent') or "
            "contains(translate(., 'CONSENTACCEPTAGREEOK', 'consentacceptagreeok'), 'accept') or "
            "contains(translate(., 'CONSENTACCEPTAGREEOK', 'consentacceptagreeok'), 'agree') or "
            "contains(., 'OK')]"
        )
        if consent_btn.is_displayed() and consent_btn.is_enabled():
            consent_btn.click()
            time.sleep(0.5)  # Reduced sleep for stability
            print('Consent popup closed.')
    except Exception:
        pass

while True:
    handle_consent_popup()
    # Scroll the table body to the bottom to render all rows (if virtualized)
    try:
        table_body = driver.find_element(By.CSS_SELECTOR, "table tbody")
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", table_body)
        time.sleep(0.2)  # Reduced sleep for stability
    except Exception:
        pass

    # Get table headers
    if not headers:
        headers = [th.text.strip() for th in driver.find_elements(By.CSS_SELECTOR, "table thead th")]

    # Get table data for this page
    page_data = get_table_data()
    new_rows = []
    for row in page_data:
        if row and row[0] not in seen_symbols:
            seen_symbols.add(row[0])
            new_rows.append(row)
    all_rows.extend(new_rows)
    print(f"Page {page} accessed, data scraped: {len(new_rows)} new, {len(all_rows)} total.")
    page += 1

    # Scroll the page to about 60% height to make Next button visible but not covered
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
    time.sleep(0.1)  # Reduced sleep for stability

    # Try to click the "Next" button
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(),'Next')]]")))
        next_btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(),'Next')]]")
        if "disabled" in next_btn.get_attribute("class"):
            break  # No more pages
        first_symbol_before = page_data[0][0] if page_data and page_data[0] else None
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
        time.sleep(0.1)  # Reduced sleep for stability
        driver.execute_script("arguments[0].click();", next_btn)
        WebDriverWait(driver, 10).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "table tbody tr") and
                      d.find_elements(By.CSS_SELECTOR, "table tbody tr")[0].find_elements(By.TAG_NAME, "td") and
                      d.find_elements(By.CSS_SELECTOR, "table tbody tr")[0].find_elements(By.TAG_NAME, "td")[0].text != first_symbol_before
        )
        time.sleep(0.2)  # Reduced sleep for stability
    except Exception:
        break

driver.quit()

# Remove duplicate rows (if any)
unique_rows = [list(x) for x in set(tuple(row) for row in all_rows)]

# Add today's date and AM/PM to each row
now = datetime.now()
current_date = now.strftime('%Y-%m-%d')
am_pm = now.strftime('%p')
unique_rows_with_date = [row + [current_date, am_pm] for row in unique_rows]

# Prepare headers with date and AM/PM
headers_with_date = headers + ['Date', 'AM/PM']

# Check if file exists to determine if we need to write headers
file_exists = os.path.isfile('stocks.csv')

# Save to CSV (append mode)
df = pd.DataFrame(unique_rows_with_date, columns=headers_with_date)
if file_exists:
    write_header = os.stat('stocks.csv').st_size == 0
    df.to_csv('stocks.csv', mode='a', header=write_header, index=False)
else:
    df.to_csv('stocks.csv', mode='w', header=True, index=False)
print(f"Appended {len(df)} unique stocks to stocks.csv with date {current_date} {am_pm}") 