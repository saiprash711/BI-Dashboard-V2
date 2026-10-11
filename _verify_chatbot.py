"""
Throwaway harness: drives the assistant dock through Streamlit's AppTest.

Covers the parts the offline assistant test cannot reach — that the launcher and
panel actually render as widgets, that the turn cycle completes, and that the
CSS the layout depends on is present in the page.
"""
import re

from streamlit.testing.v1 import AppTest


def html_of(at) -> str:
    return " ".join((getattr(e, "body", "") or "") for e in at.get("html"))


def plain(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def keys(at) -> list[str]:
    return [b.key for b in at.button]


def show(at, label: str) -> None:
    print(f"\n--- {label} ---")
    print("  exceptions :", [e.value for e in at.exception])
    print("  buttons    :", keys(at))
    print("  chat inputs:", len(at.chat_input))


def has_state(at, key: str) -> bool:
    # AppTest's session_state proxy exposes no .get(), so membership is the way.
    return key in at.session_state


def turn(at, msgs: list[dict]) -> tuple[dict, dict]:
    """Return the (question, answer) pair at the end of a conversation."""
    assert len(msgs) >= 2, f"expected a full turn, got {msgs}"
    return msgs[-2], msgs[-1]


at = AppTest.from_file("app.py", default_timeout=300).run()
assert not at.exception, at.exception[0].value

# ── sign in ─────────────────────────────────────────────────────────────────
at.text_input(key="lg_user").set_value("analyst")
at.text_input(key="lg_pass").set_value("Analyst@2026")
at.button[0].click().run()
assert not at.exception, at.exception[0].value
assert len(at.tabs) >= 4, "dashboard did not load"
show(at, "signed in, panel closed")

# ── launcher present and closed ─────────────────────────────────────────────
assert "kb_toggle_off" in keys(at), "launcher button missing when panel is shut"
assert "kb_toggle_on" not in keys(at), "panel-open launcher rendered too early"
assert not at.chat_input, "chat input visible before the panel was opened"
assert at.session_state["kb_open"] is False

css = html_of(at)
for selector in (".st-key-kb_dock", ".st-key-kb_panel", "kbBounce", "kbSonar",
                 "kbPop", "kbDot", "kb-msgs", "st-key-kb_chip_",
                 "prefers-reduced-motion"):
    assert selector in css, f"chat stylesheet missing {selector!r}"
for selector in ("fxRise", "fxSweep", "fxAuroraA", ".kpi", ".hero h1"):
    assert selector in css, f"motion layer missing {selector!r}"
print("  stylesheets: chat + motion layer both injected")

# ── open it ─────────────────────────────────────────────────────────────────
at.button(key="kb_toggle_off").click().run()
show(at, "panel open")
assert not at.exception, at.exception[0].value
assert at.session_state["kb_open"] is True
assert "kb_toggle_on" in keys(at), "launcher did not switch to its open state"
assert "kb_clear" in keys(at) and "kb_close" in keys(at), "panel header buttons missing"
assert len(at.chat_input) == 1, "chat input did not render inside the panel"

msgs = at.session_state["kb_msgs"]
assert len(msgs) == 1 and msgs[0]["role"] == "bot", f"no opening message: {msgs}"
opening = plain(msgs[0]["html"])
assert "Records in view" in opening, opening
print("  opening    :", opening[:100])

chips = [k for k in keys(at) if k.startswith("kb_chip_")]
assert chips, "no suggestion chips rendered"
print("  chips      :", [b.label for b in at.button if b.key in chips])

# ── the typing state, checked at the source ─────────────────────────────────
# AppTest follows st.rerun() chains synchronously, so a whole turn resolves
# inside one run() and the intermediate frame is never observable from here.
# The indicator is verified against the renderer instead.
import chatbot as CB                                        # noqa: E402

mid = CB._messages_html([{"role": "user", "text": "hi"}], thinking=True)
assert "kb-typing" in mid and mid.count("<i></i>") == 3, mid
settled = CB._messages_html([{"role": "user", "text": "hi"},
                             {"role": "bot", "html": "<p>x</p>", "chips": []}], False)
assert "kb-typing" not in settled, settled
# Newest first in the DOM; CSS column-reverse flips it so it lands at the bottom.
assert settled.index("<p>x</p>") < settled.index("hi"), settled
print("  typing     : indicator renders while thinking, absent once answered")

# ── ask a question through the chat input ───────────────────────────────────
at.chat_input[0].set_value("top 5 states by revenue").run()
assert not at.exception, at.exception[0].value
assert at.session_state["kb_pending"] is None, "question never cleared"
assert at.session_state["kb_thinking"] is False, "thinking flag left set"

question, answer = turn(at, at.session_state["kb_msgs"])
assert question["role"] == "user" and question["text"] == "top 5 states by revenue", question
assert answer["role"] == "bot", f"no answer appended: {at.session_state['kb_msgs']}"
body = plain(answer["html"])
print("\n--- answered ---\n ", body[:190])
assert "State by commission revenue" in body, body
assert "Cr" in body or "L" in body, "no currency figure in the answer"
# The stylesheet itself mentions .kb-typing, so match the bubble markup instead.
assert "kb-bub kb-typing" not in html_of(at), "typing indicator outlived the answer"

# ── a chip click also asks a question ───────────────────────────────────────
before = len(at.session_state["kb_msgs"])
chip = [b for b in at.button if b.key == "kb_chip_0"][0]
label = chip.label
chip.click().run()
assert not at.exception, at.exception[0].value
after = at.session_state["kb_msgs"]
assert len(after) == before + 2, f"chip did not produce a turn: {len(after)} vs {before}"
assert after[-2]["text"] == label, after[-2]
print(f"\n--- chip '{label}' ---\n ", plain(after[-1]["html"])[:160])

# ── clear, close, and reopen ────────────────────────────────────────────────
at.button(key="kb_clear").click().run()
assert not at.exception, at.exception[0].value
# Cleared, then immediately reseeded with a fresh opening message.
assert len(at.session_state["kb_msgs"]) == 1, at.session_state["kb_msgs"]
print("\n--- cleared ---\n  history reset to the opening message")

at.button(key="kb_close").click().run()
assert not at.exception, at.exception[0].value
assert at.session_state["kb_open"] is False
assert not at.chat_input, "panel still rendering after close"
assert "kb_toggle_off" in keys(at)
print("--- closed ---\n  panel dismissed, launcher back to its bouncing state")

# ── logout must not leave a conversation behind ─────────────────────────────
at.button(key="kb_toggle_off").click().run()
at.chat_input[0].set_value("total gmv").run()
assert len(at.session_state["kb_msgs"]) >= 3, at.session_state["kb_msgs"]
logout = [b for b in at.sidebar.button if b.key == "logout_btn"][0]
logout.click().run()
assert not at.exception, at.exception[0].value
assert at.session_state["auth_user"] is None
assert not has_state(at, "kb_msgs") or not at.session_state["kb_msgs"], \
    "conversation survived sign-out"
assert not has_state(at, "kb_open") or at.session_state["kb_open"] is False, \
    "assistant still open after sign-out"
print("\n--- signed out ---\n  conversation discarded with the session")

print("\nALL CHECKS PASSED")
