"""
Throwaway probe: collapse the sidebar, prove the reopen control is a visible
labelled pill, and prove clicking it brings the filter stack back.
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PORT = sys.argv[1] if len(sys.argv) > 1 else "8612"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--force-device-scale-factor=1")
opts.add_argument("--hide-scrollbars")
d = webdriver.Chrome(options=opts)

JS_BOX = """
const el = document.querySelector(arguments[0]);
if (!el) return null;
const r = el.getBoundingClientRect();
const cs = getComputedStyle(el);
const after = getComputedStyle(el, '::after');
return {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height),
        display:cs.display, vis:cs.visibility, op:cs.opacity,
        bg:cs.backgroundColor, border:cs.borderTopColor,
        label:after.content, labelColor:after.color};
"""
fails = []


def n_expanders():
    return d.execute_script(
        "return document.querySelectorAll('section[data-testid=\"stSidebar\"] "
        "[data-testid=\"stExpander\"]').length;")


try:
    d.get(f"http://127.0.0.1:{PORT}")
    time.sleep(14)
    ins = d.find_elements(By.CSS_SELECTOR, ".st-key-login_card input")
    if not ins:
        d.save_screenshot("_probe_nologin.png")
        raise SystemExit("no login inputs")
    ins[0].send_keys("analyst")
    ins[1].send_keys("Analyst@2026")
    d.find_element(By.CSS_SELECTOR,
                   '.st-key-login_card [data-testid="stFormSubmitButton"] button').click()
    time.sleep(25)

    print("expanded:")
    print("  filter expanders:", n_expanders())
    if n_expanders() < 5:
        fails.append(f"only {n_expanders()} filter cards rendered")
    chev = d.execute_script(JS_BOX, '[data-testid="stSidebarCollapseButton"] button')
    print("  collapse chevron:", chev)
    if chev is None or chev["vis"] != "visible":
        fails.append(f"collapse chevron not visible without hover: {chev}")

    d.execute_script(
        "document.querySelector('[data-testid=\"stSidebarCollapseButton\"] button').click();")
    time.sleep(5)
    d.save_screenshot("_probe_collapsed.png")

    print("\ncollapsed:")
    print("  sidebar:", d.execute_script(JS_BOX, 'section[data-testid="stSidebar"]'))
    pill = d.execute_script(JS_BOX, '[data-testid="stExpandSidebarButton"]')
    print("  reopen pill:", pill)
    if pill is None:
        fails.append("no reopen control rendered while collapsed")
    else:
        if pill["vis"] != "visible" or pill["op"] == "0":
            fails.append(f"reopen control not visible: {pill}")
        if "Filters" not in (pill["label"] or ""):
            fails.append(f"reopen control carries no label: {pill['label']!r}")
        if pill["w"] < 70:
            fails.append(f"reopen control is only {pill['w']}px wide, label not laid out")
        if pill["bg"] in ("rgba(0, 0, 0, 0)", "transparent"):
            fails.append(f"reopen control has no fill: {pill['bg']}")

        top = d.execute_script("""
          const b = document.querySelector('[data-testid="stExpandSidebarButton"]');
          const r = b.getBoundingClientRect();
          const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
          return el ? el.tagName + '.' + (el.className||'').toString().slice(0,50) : null;
        """)
        print("  topmost at pill centre:", top)
        if top is None:
            fails.append("nothing hit-tests at the reopen control")

        d.find_element(By.CSS_SELECTOR, '[data-testid="stExpandSidebarButton"]').click()
        time.sleep(6)
        d.save_screenshot("_probe_reopened.png")
        sb = d.execute_script(JS_BOX, 'section[data-testid="stSidebar"]')
        print("\nreopened:")
        print("  sidebar:", sb)
        print("  filter expanders:", n_expanders())
        if sb is None or sb["w"] < 200 or sb["x"] < 0:
            fails.append(f"sidebar did not come back: {sb}")
        if n_expanders() < 5:
            fails.append(f"filters did not come back ({n_expanders()} cards)")
        txt = d.execute_script(
            "const e=document.querySelector('section[data-testid=\"stSidebar\"]');"
            "return e ? e.innerText : '';")
        for word in ("FILTERS", "Financial year", "Month", "State"):
            if word not in txt:
                fails.append(f"'{word}' missing from the reopened sidebar")
finally:
    d.quit()

print()
if fails:
    print(f"FAILURES ({len(fails)}):")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("collapse -> reopen verified: the filter rail is always recoverable")
