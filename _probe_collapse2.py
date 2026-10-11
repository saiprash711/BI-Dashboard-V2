"""Throwaway probe: what reopen affordance exists once the sidebar is collapsed?"""
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

try:
    d.get(f"http://127.0.0.1:{PORT}")
    time.sleep(14)
    ins = d.find_elements(By.CSS_SELECTOR, ".st-key-login_card input")
    ins[0].send_keys("analyst")
    ins[1].send_keys("Analyst@2026")
    d.find_element(By.CSS_SELECTOR,
                   '.st-key-login_card [data-testid="stFormSubmitButton"] button').click()
    time.sleep(25)

    print("EXPANDED header html:")
    print(d.execute_script(
        "const h=document.querySelector('[data-testid=\"stHeader\"]');"
        "return h ? h.outerHTML.slice(0,1500) : null;"))

    btn = d.find_element(By.CSS_SELECTOR, '[data-testid="stSidebarCollapseButton"] button')
    print("\ncollapse button:", d.execute_script(
        "const cs=getComputedStyle(arguments[0]); const r=arguments[0].getBoundingClientRect();"
        "return {testid:arguments[0].getAttribute('data-testid'),"
        "parent:arguments[0].parentElement.getAttribute('data-testid'),"
        "opacity:cs.opacity, vis:cs.visibility, x:Math.round(r.x), y:Math.round(r.y),"
        "w:Math.round(r.width), h:Math.round(r.height)};", btn))

    d.execute_script("arguments[0].click();", btn)
    time.sleep(5)
    d.save_screenshot("_probe_collapsed.png")

    print("\nCOLLAPSED header html:")
    print(d.execute_script(
        "const h=document.querySelector('[data-testid=\"stHeader\"]');"
        "return h ? h.outerHTML.slice(0,2500) : null;"))

    print("\nall testids containing 'ollaps' or 'idebar':")
    print(d.execute_script("""
      return [...document.querySelectorAll('[data-testid]')]
        .map(e => e.getAttribute('data-testid'))
        .filter(t => /ollaps|idebar/i.test(t));
    """))

    print("\nvisible buttons in top-left 400x120 region:")
    print(d.execute_script("""
      return [...document.querySelectorAll('button')].map(b => {
        const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
        return {t:(b.getAttribute('data-testid')||b.getAttribute('kind')||b.className.toString().slice(0,40)),
                x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height),
                op:cs.opacity, vis:cs.visibility, disp:cs.display};
      }).filter(o => o.x < 400 && o.y < 120);
    """))
finally:
    d.quit()
