"""Throwaway probe: is the sidebar filter stack present and reachable after sign-in?"""
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PORT = sys.argv[1] if len(sys.argv) > 1 else "8611"

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
return {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height),
        display:cs.display, visibility:cs.visibility, opacity:cs.opacity,
        transform:cs.transform, aria:el.getAttribute('aria-expanded')};
"""

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
    d.save_screenshot("_probe_after_login.png")

    for name, sel in [
        ("sidebar", 'section[data-testid="stSidebar"]'),
        ("collapsed control", '[data-testid="stSidebarCollapsedControl"]'),
        ("header", '[data-testid="stHeader"]'),
        ("sb content", 'section[data-testid="stSidebar"] [data-testid="stSidebarContent"]'),
        ("filters head", '.flt-head'),
        ("reset btn", '.st-key-flt_reset'),
        ("first expander", 'section[data-testid="stSidebar"] [data-testid="stExpander"]'),
    ]:
        print(f"  {name:<20} {d.execute_script(JS_BOX, sel)}")

    n_exp = d.execute_script(
        "return document.querySelectorAll('section[data-testid=\"stSidebar\"] "
        "[data-testid=\"stExpander\"]').length;")
    print("  expanders in sidebar:", n_exp)
    print("  sidebar text:", (d.execute_script(
        "const e=document.querySelector('section[data-testid=\"stSidebar\"]');"
        "return e ? e.innerText.replace(/\\n/g,' | ') : null;") or "")[:600])

    # any leftover login stylesheet hiding the sidebar?
    hiders = d.execute_script("""
      const out=[];
      for (const s of document.styleSheets) {
        let rules; try { rules = s.cssRules; } catch(e) { continue; }
        for (const r of rules) {
          if (r.selectorText && r.selectorText.includes('stSidebar')
              && /display\\s*:\\s*none/.test(r.cssText)) out.push(r.cssText.slice(0,160));
        }
      }
      return out;
    """)
    print("  rules hiding sidebar:", hiders)

    if n_exp:
        print("  header stacking:", d.execute_script(
            "const h=document.querySelector('[data-testid=\"stHeader\"]');"
            "const c=document.querySelector('[data-testid=\"stSidebarCollapsedControl\"]');"
            "return {hRect:h&&h.getBoundingClientRect().height,"
            "hOverflow:h&&getComputedStyle(h).overflow, cVis:c&&getComputedStyle(c).visibility};"))
finally:
    d.quit()
