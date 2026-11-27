from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(channel="msedge", headless=True)
    for size,name in [(512,'icon-512.png'),(192,'icon-192.png'),(180,'icon-180.png')]:
        pg=b.new_page(viewport={"width":size,"height":size}, device_scale_factor=1)
        pg.goto(f"file:///D:/Program%20Files/Tencent/2026-11-18-19-16-21/daimon-mes/frontend/_icon_{size}.html")
        pg.wait_for_timeout(300)
        pg.screenshot(path=f"frontend/public/{name}" if False else f"public/{name}")
        pg.close()
    b.close()
print("icons ok")
