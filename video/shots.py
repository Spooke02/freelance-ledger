from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)
    p = b.new_page(viewport={"width": 1280, "height": 720}, color_scheme="dark")
    p.goto("http://127.0.0.1:8765/"); p.wait_for_selector(".ag-row")
    p.select_option("#src", "demo"); p.wait_for_timeout(1500)
    p.wait_for_function("document.getElementById('msg').textContent===''")
    p.screenshot(path="thumbs/_shot_demo.png")
    p.select_option("#src", "paypal"); p.wait_for_function("document.body.innerText.includes('John Doe')"); p.wait_for_timeout(800)
    p.screenshot(path="thumbs/_shot_paypal.png")
    b.close()
