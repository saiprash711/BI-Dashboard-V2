"""Throwaway: dump what the panel actually put in the DOM after a question."""
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PORT = sys.argv[1] if len(sys.argv) > 1 else "8599"
opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1000")
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
    time.sleep(22)
    d.find_element(By.CSS_SELECTOR, ".st-key-kb_dock button").click()
    time.sleep(14)

    ta = d.find_element(By.CSS_SELECTOR,
                        '.st-key-kb_panel [data-testid="stChatInput"] textarea')
    ta.send_keys("top 5 sellers by gmv")
    ta.send_keys("\n")

    for wait in (3, 6, 10, 16):
        time.sleep(wait if wait == 3 else wait - 3)
        n = d.execute_script(
            "return document.querySelectorAll('.st-key-kb_panel .kb-m').length;")
        typing = d.execute_script(
            "return document.querySelectorAll('.st-key-kb_panel .kb-typing').length;")
        print(f"t+{wait:>2}s  bubbles={n}  typing={typing}")

    print("\n--- outer HTML of the newest bubble ---")
    html = d.execute_script(
        "const e=document.querySelector('.st-key-kb_panel .kb-msgs');"
        "return e ? e.firstElementChild.outerHTML : 'NO MSGS';")
    print(html[:2600])

    print("\n--- class names present inside the panel ---")
    cls = d.execute_script("""
      const s = new Set();
      document.querySelectorAll('.st-key-kb_panel *').forEach(e => {
        (e.className||'').toString().split(/\\s+/).forEach(c => {
          if (c.startsWith('kb-')) s.add(c);});});
      return [...s].sort();
    """)
    print(cls)
finally:
    d.quit()
