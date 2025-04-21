
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    # context manager
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()
    page.goto("https://bandcamp.com/discover/hip-hop-rap")

    # <button data-v-922c8136="" data-v-bfd14257="" class="g-button outline"><!----><!---->Accept necessary only</button>
    page.wait_for_selector('button.g-button.outline')

    try:
        page.click('button.g-button.outline', timeout=3000)
    except: # JS trick
        print("Regular click failed, trying JS-based force click.")
        buttons = page.query_selector_all('button.g-button.outline')
        print(f"Found {len(buttons)} buttons")

        for i, btn in enumerate(buttons):
            label = btn.inner_text().strip().lower()
            if "necessary" in label or "accept" in label:
                print(f"Clicking button #{i} with text: {label}")
                page.evaluate("(btn) => btn.click()", btn)
                break
    
    # <div data-v-77d1b95b="" data-v-662ed65e="" class="results-grid" style="--2b8079fc: 
    page.is_visible('ul.items') # results-grid but only albums
    html = page.inner_html('div.results-grid')
    soup = BeautifulSoup(html, 'html.parser')
    #print(soup.find_all('span'))

    # getting artists and storing in a list
    artists = [span.text.replace("by ", "") for span in soup.find_all('span') if span.text.startswith("by ")]
    print(artists)

   