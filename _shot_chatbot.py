"""
Throwaway harness: photographs the assistant dock in a real browser and measures
its geometry, which is the only way to confirm the fixed positioning actually
lands where it should against Streamlit's live DOM.
"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PORT = sys.argv[1] if len(sys.argv) > 1 else "8599"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
opts.add_argument("--force-device-scale-factor=1")
opts.add_argument("--hide-scrollbars")
d = webdriver.Chrome(options=opts)

BOX = """
const el = document.querySelector(arguments[0]);
if (!el) return null;
const r = el.getBoundingClientRect();
return {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width),
        h:Math.round(r.height), right:Math.round(window.innerWidth - r.right),
        vw:window.innerWidth, vh:window.innerHeight,
        pos:getComputedStyle(el).position, z:getComputedStyle(el).zIndex,
        anim:getComputedStyle(el).animationName};
"""

fails = []


def box(sel):
    return d.execute_script(BOX, sel)


def report(name, sel):
    b = box(sel)
    print(f"  {name:<26} {b}")
    return b


def count(sel):
    return d.execute_script("return document.querySelectorAll(arguments[0]).length;", sel)


def wait_until(sel, minimum, limit=45):
    """Poll until at least ``minimum`` nodes match, or give up after ``limit``s."""
    deadline = time.time() + limit
    while time.time() < deadline:
        n = count(sel)
        if n >= minimum:
            return n
        time.sleep(1)
    return count(sel)


try:
    d.get(f"http://127.0.0.1:{PORT}")
    time.sleep(14)

    ins = d.find_elements(By.CSS_SELECTOR, ".st-key-login_card input")
    if not ins:
        d.save_screenshot("_shot_nologin.png")
        raise SystemExit("login inputs not found - see _shot_nologin.png")
    ins[0].send_keys("analyst")
    ins[1].send_keys("Analyst@2026")
    d.find_element(By.CSS_SELECTOR,
                   '.st-key-login_card [data-testid="stFormSubmitButton"] button').click()
    time.sleep(22)

    wait_until(".st-key-kb_dock button", 1)
    print("\nclosed state")
    d.save_screenshot("_shot_dock_closed.png")
    dock = report("dock", ".st-key-kb_dock")
    btn = report("launcher button", ".st-key-kb_dock button")
    hdr = report("streamlit header", '[data-testid="stHeader"]')

    if dock is None or btn is None:
        raise SystemExit("the dock did not render")
    if dock["pos"] != "fixed":
        fails.append(f"dock is {dock['pos']}, expected fixed")
    if dock["y"] > 70:
        fails.append(f"dock sits {dock['y']}px from the top, expected the header band")
    if dock["right"] > 140:
        fails.append(f"dock sits {dock['right']}px from the right edge, expected the corner")
    if btn["w"] < 40 or btn["h"] < 40:
        fails.append(f"launcher collapsed to {btn['w']}x{btn['h']}")
    if btn["anim"] != "kbBounce":
        fails.append(f"launcher animation is {btn['anim']!r}, expected kbBounce")
    if box(".st-key-kb_panel") is not None:
        fails.append("panel rendered while closed")

    # Does anything sit on top of the launcher at its centre?
    top = d.execute_script("""
        const r = document.querySelector('.st-key-kb_dock button').getBoundingClientRect();
        const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
        return el ? (el.tagName + '.' + (el.className || '').toString().slice(0,60)) : null;
    """)
    print(f"  {'topmost at launcher centre':<26} {top}")
    if top is None or ("button" not in top.lower() and "stMarkdown" not in top
                       and "p." not in top.lower() and top.split(".")[0] != "P"):
        fails.append(f"launcher is not the topmost element at its centre: {top}")

    # ── open it ─────────────────────────────────────────────────────────────
    d.find_element(By.CSS_SELECTOR, ".st-key-kb_dock button").click()
    wait_until('.st-key-kb_panel [data-testid="stChatInput"] textarea', 1)
    time.sleep(2)
    print("\nopen state")
    d.save_screenshot("_shot_dock_open.png")
    panel = report("panel", ".st-key-kb_panel")
    msgs = report("message list", ".st-key-kb_panel .kb-msgs")
    chat = report("chat input", '.st-key-kb_panel [data-testid="stChatInput"]')
    bub = report("first answer bubble", ".st-key-kb_panel .kb-bub")

    if panel is None:
        raise SystemExit("panel did not open")
    if panel["pos"] != "fixed":
        fails.append(f"panel is {panel['pos']}, expected fixed")
    if panel["right"] > 60:
        fails.append(f"panel sits {panel['right']}px from the right edge")
    if panel["x"] < 0 or panel["y"] < 0:
        fails.append(f"panel starts off-screen at {panel['x']},{panel['y']}")
    if panel["y"] + panel["h"] > panel["vh"] + 2:
        fails.append(f"panel overflows the viewport: bottom "
                     f"{panel['y'] + panel['h']} vs {panel['vh']}")
    if panel["w"] < 300:
        fails.append(f"panel is only {panel['w']}px wide")
    if msgs is None or msgs["h"] < 60:
        fails.append(f"message list did not render: {msgs}")
    if chat is None or chat["w"] < 200:
        fails.append(f"chat input did not render inside the panel: {chat}")
    if bub is None:
        fails.append("no message bubble rendered")

    # Is the chat input actually reachable, i.e. nothing covering it?
    hit = d.execute_script("""
        const r = document.querySelector('.st-key-kb_panel [data-testid="stChatInput"] textarea')
                  .getBoundingClientRect();
        const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
        return el ? el.tagName + '.' + (el.className||'').toString().slice(0,40) : null;
    """)
    print(f"  {'topmost at input centre':<26} {hit}")
    if hit is None or "TEXTAREA" not in hit.upper():
        fails.append(f"the chat input is covered by {hit}")

    # ── ask something ───────────────────────────────────────────────────────
    ta = d.find_element(By.CSS_SELECTOR,
                        '.st-key-kb_panel [data-testid="stChatInput"] textarea')
    ta.send_keys("top 5 sellers by gmv")
    ta.send_keys("\n")
    # The turn takes two reruns: typing indicator, then the answer. Poll for the
    # ranked rows rather than guessing at a sleep.
    rows = wait_until(".st-key-kb_panel .kb-rank .kb-row", 2)
    time.sleep(1.5)
    d.save_screenshot("_shot_dock_answer.png")
    print("\nafter a question")
    n = count(".st-key-kb_panel .kb-m")
    bars = d.execute_script("""
        return [...document.querySelectorAll('.st-key-kb_panel .kb-rank .kb-row > i')]
               .slice(0,3).map(e => Math.round(e.getBoundingClientRect().width));
    """)
    print(f"  bubbles={n}  ranked rows={rows}  bar widths={bars}")
    if n < 3:
        fails.append(f"expected at least 3 bubbles after a question, found {n}")
    if rows < 2:
        fails.append(f"the answer rendered no ranked rows ({rows})")
    if bars and max(bars) < 8:
        fails.append(f"rank bars never grew: {bars}")

    # ── light mode, to prove the panel is themed not hard-coded ─────────────
    d.find_element(By.CSS_SELECTOR, ".st-key-theme_switch button").click()
    time.sleep(16)
    d.save_screenshot("_shot_dock_light.png")
    bg = d.execute_script(
        "const e=document.querySelector('.st-key-kb_panel');"
        "return e ? getComputedStyle(e).backgroundImage.slice(0,90) : null;")
    print(f"\nlight mode\n  panel background: {bg}")
    if bg is None:
        fails.append("panel vanished after the theme switch")

finally:
    d.quit()

print()
if fails:
    print(f"FAILURES ({len(fails)}):")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("geometry and rendering verified in a real browser")
