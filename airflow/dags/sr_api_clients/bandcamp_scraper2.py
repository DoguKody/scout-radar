
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    # context manager
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()
    page.goto("https://bandcamp.com/discover")

    # <button data-v-922c8136="" data-v-bfd14257="" class="g-button outline"><!----><!---->Accept necessary only</button>
    page.wait_for_selector('button.g-button.outline')

    overlay = page.query_selector(".overlay-background")
    if overlay and overlay.is_visible():
        print("Overlay is visible and blocking clicks.")
    
    page.evaluate("""() => {
    const overlay = document.querySelector('.overlay-background');
    if (overlay) overlay.remove();
    }""")

    page.click('button.g-button.outline')
    

    # PlayWright -> HTML -> SoupObject -> soup.find()

    # <div data-v-e0760e9e="" class="meta">
    # OR <div data-v-77d1b95b="" data-v-662ed65e="" class="results-grid" style="--2b8079fc: 
    #html = page.inner_html('#image-carousel-slide-uid385')
    #print(html)

    # <div data-v-77d1b95b="" data-v-662ed65e="" class="results-grid" style="--2b8079fc: var(--bc-font-weight-medium);"><ul data-v-77d1b95b=""
    

   