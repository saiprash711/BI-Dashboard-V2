"""
The floating assistant dock — launcher, panel and conversation state.

Layout strategy
---------------
Streamlit has no floating-window primitive, so the dock is built from two
keyed containers that CSS lifts out of the document flow:

    st.container(key="kb_dock")    → the round launcher, pinned top-right
    st.container(key="kb_panel")   → the conversation panel beneath it

``st.container(key=...)`` stamps an ``st-key-<key>`` class onto the element's
outermost div, which is the only hook the stylesheet needs. Everything inside
stays a real Streamlit widget, so ``st.chat_input`` keeps its Enter-to-send
behaviour and the buttons keep their callbacks.

The message list is rendered as one HTML block in ``column-reverse`` order.
That keeps the newest bubble against the bottom edge and makes the scroller
open at the bottom without any JavaScript, which Streamlit would strip anyway.

Turn cycle
----------
A question is answered on the run *after* it is asked, so the panel can paint a
typing indicator first:

    click / submit  → kb_pending set                    (callback, then rerun)
    run A           → kb_thinking set, typing bubble drawn, short pause, rerun
    run B           → assistant.answer() runs, bubble replaced by the reply
"""
from __future__ import annotations

import time
from html import escape

import streamlit as st

import assistant

# How long the typing indicator stays up. Long enough to read as a beat of
# thought, short enough that it never feels like latency.
_THINK_PAUSE = 0.45

MAX_CHIPS = 4


# ═════════════════════════════════════════════════════════════════════════════
# STYLESHEET
#
# Injected through st.html() for the same reason as the main sheet: Markdown
# would treat a blank line as the end of the raw-HTML block. _css() strips
# blank lines and indentation so the payload is safe either way.
# ═════════════════════════════════════════════════════════════════════════════
_CSS_BODY = """
/* ═══ LAUNCHER ══════════════════════════════════════════════════════════ */
.st-key-kb_dock{
  position:fixed !important; top:.42rem; right:4.4rem; z-index:1000001;
  width:52px !important; height:52px; flex:none !important;
  pointer-events:none;
}
.st-key-kb_dock > *{pointer-events:auto;}
.st-key-kb_dock [data-testid="stElementContainer"]{width:52px !important;}

/* Two expanding sonar rings, offset by half a cycle */
.st-key-kb_dock::before, .st-key-kb_dock::after{
  content:""; position:absolute; inset:2px; border-radius:50%;
  border:1.5px solid var(--jade); opacity:0; pointer-events:none;
  animation:kbSonar 2.9s cubic-bezier(.2,.7,.3,1) infinite;
}
.st-key-kb_dock::after{animation-delay:1.45s;}
@keyframes kbSonar{
  0%{transform:scale(.82); opacity:.6;}
  70%{opacity:0;}
  100%{transform:scale(2.15); opacity:0;}
}

/* Rotating gradient halo, sitting behind the button */
.st-key-kb_dock .stButton{position:relative; width:52px;}
.st-key-kb_dock .stButton::before{
  content:""; position:absolute; inset:-4px; border-radius:50%; z-index:0;
  background:conic-gradient(from 0turn,var(--jade),var(--violet),var(--amber),var(--teal),var(--jade));
  filter:blur(6px); opacity:.75;
  animation:kbSpin 3.6s linear infinite;
}
@keyframes kbSpin{to{transform:rotate(1turn);}}

.st-key-kb_dock button{
  position:relative; z-index:1;
  width:52px !important; height:52px !important; min-height:0 !important;
  padding:0 !important; border-radius:50% !important; border:none !important;
  background:radial-gradient(circle at 32% 26%,rgba(255,255,255,.34),transparent 58%),
             linear-gradient(140deg,var(--jade),var(--violet)) !important;
  box-shadow:0 12px 28px -10px rgba(0,229,160,.85),
             inset 0 0 0 1px rgba(255,255,255,.22) !important;
  animation:kbBounce 2.3s cubic-bezier(.3,.7,.4,1) infinite;
  transition:transform .2s cubic-bezier(.2,.9,.3,1.4), box-shadow .2s;
}
.st-key-kb_dock button p{
  font-size:1.32rem !important; line-height:1 !important; font-weight:400 !important;
  color:#04231A !important; margin:0 !important;
  text-shadow:0 1px 0 rgba(255,255,255,.35);
}
.st-key-kb_dock button:hover{
  animation-play-state:paused;
  transform:scale(1.14) rotate(-8deg);
  box-shadow:0 16px 36px -8px rgba(0,229,160,1) !important;
}
.st-key-kb_dock button:active{transform:scale(.94);}
.st-key-kb_dock button:focus{outline:none !important;}

/* The squash-and-stretch bounce the whole dock is built around */
@keyframes kbBounce{
  0%,100%{transform:translateY(0) scale(1,1);}
  10%{transform:translateY(1px) scale(1.09,.91);}
  28%{transform:translateY(-10px) scale(.94,1.07);}
  46%{transform:translateY(0) scale(1.07,.93);}
  60%{transform:translateY(-4px) scale(.98,1.02);}
  74%{transform:translateY(0) scale(1.03,.97);}
  86%{transform:translateY(-1px) scale(1,1);}
}

/* Attention pip — only while the panel is shut */
.st-key-kb_toggle_off button::after{
  content:""; position:absolute; top:-2px; right:-2px;
  width:13px; height:13px; border-radius:50%;
  background:var(--amber); border:2.5px solid var(--bg);
  animation:kbPip 1.25s cubic-bezier(.3,.7,.4,1) infinite;
}
@keyframes kbPip{
  0%,100%{transform:translateY(0) scale(1);}
  35%{transform:translateY(-5px) scale(1.14);}
  70%{transform:translateY(0) scale(.92,1.08);}
}
.st-key-kb_toggle_on button{
  background:linear-gradient(140deg,var(--surface-3),var(--surface-2)) !important;
  box-shadow:0 10px 24px -12px rgba(0,0,0,.9),
             inset 0 0 0 1px var(--border-strong) !important;
  animation:none; transform:rotate(0deg);
}
.st-key-kb_toggle_on button p{color:var(--muted) !important; font-size:1.05rem !important;
  text-shadow:none;}
.st-key-kb_toggle_on button:hover{transform:scale(1.1) rotate(90deg);}

/* ═══ PANEL ═════════════════════════════════════════════════════════════ */
.st-key-kb_panel{
  position:fixed !important; top:4.15rem; right:1.15rem; z-index:1000000;
  width:min(29rem,calc(100vw - 2.3rem)) !important;
  max-height:calc(100vh - 5.4rem);
  overflow-y:auto; overflow-x:hidden;
  padding:.9rem .95rem .55rem !important;
  border:1px solid var(--border-strong); border-radius:20px;
  background:linear-gradient(168deg,var(--surface-2) 0%,var(--surface) 62%,var(--surface-2) 100%);
  box-shadow:0 36px 90px -26px rgba(0,0,0,.9),0 0 0 1px var(--jade-line),
             0 0 46px -20px var(--jade-soft);
  animation:kbPop .5s cubic-bezier(.16,1.42,.4,1) both;
  scrollbar-width:thin;
}
.st-key-kb_panel::before{
  content:""; position:absolute; left:16px; right:16px; top:0; height:2px;
  border-radius:2px; pointer-events:none;
  background:linear-gradient(90deg,transparent,var(--jade),var(--violet),var(--amber),transparent);
  background-size:220% 100%;
  animation:kbFlow 4.5s linear infinite;
}
@keyframes kbFlow{0%{background-position:200% 0;}100%{background-position:-20% 0;}}
@keyframes kbPop{
  0%{opacity:0; transform:translate(14px,-22px) scale(.82);}
  55%{opacity:1;}
  100%{opacity:1; transform:translate(0,0) scale(1);}
}
.st-key-kb_panel [data-testid="stVerticalBlock"]{gap:.5rem !important;}
.st-key-kb_panel [data-testid="stHorizontalBlock"]{gap:.3rem !important;}

/* ═══ PANEL HEADER ══════════════════════════════════════════════════════ */
.kb-head{display:flex; align-items:center; gap:.6rem; min-width:0;}
.kb-head .kb-orb{
  width:34px; height:34px; border-radius:11px; flex:none; display:grid; place-items:center;
  font-size:.95rem; color:#04231A;
  background:linear-gradient(140deg,var(--jade),var(--violet));
  box-shadow:0 6px 16px -6px rgba(0,229,160,.8);
  animation:kbOrb 3.1s cubic-bezier(.3,.7,.4,1) infinite;
}
@keyframes kbOrb{
  0%,100%{transform:translateY(0) rotate(0deg);}
  30%{transform:translateY(-4px) rotate(-7deg);}
  60%{transform:translateY(0) rotate(5deg);}
}
.kb-head .kb-who{min-width:0;}
.kb-head .kb-who b{
  display:block; font-size:.85rem; font-weight:800; color:var(--text);
  letter-spacing:-.01em; line-height:1.2;
}
.kb-head .kb-who span{
  display:flex; align-items:center; gap:.34rem; margin-top:.12rem;
  font-size:.62rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase;
  color:var(--jade-text);
}
.kb-head .kb-who i{
  width:6px; height:6px; border-radius:50%; background:currentColor; flex:none;
  box-shadow:0 0 0 3px var(--jade-soft);
  animation:kbBeat 1.9s ease-in-out infinite;
}
@keyframes kbBeat{0%,100%{opacity:1; transform:scale(1);}50%{opacity:.35; transform:scale(.8);}}

.st-key-kb_clear button, .st-key-kb_close button{
  width:100% !important; min-height:0 !important; height:30px !important;
  padding:0 !important; border-radius:9px !important;
  background:var(--flat-soft) !important; border:1px solid var(--border) !important;
  transition:all .18s ease;
}
.st-key-kb_clear button p, .st-key-kb_close button p{
  font-size:.8rem !important; color:var(--muted) !important; margin:0 !important;
}
.st-key-kb_clear button:hover{border-color:var(--jade-line) !important;
  background:var(--jade-soft) !important; transform:rotate(-90deg);}
.st-key-kb_clear button:hover p{color:var(--jade-text) !important;}
.st-key-kb_close button:hover{border-color:var(--rose-text) !important;
  background:var(--rose-soft) !important; transform:scale(1.12);}
.st-key-kb_close button:hover p{color:var(--rose-text) !important;}

/* ═══ MESSAGE LIST ══════════════════════════════════════════════════════ */
.kb-msgs{
  display:flex; flex-direction:column-reverse; gap:.55rem;
  max-height:min(50vh,30rem); overflow-y:auto; overflow-x:hidden;
  padding:.15rem .3rem .15rem .1rem; margin:.1rem 0;
  scrollbar-width:thin; scrollbar-color:var(--scroll-thumb) transparent;
}
.kb-msgs::-webkit-scrollbar{width:6px;}
.kb-msgs::-webkit-scrollbar-thumb{background:var(--scroll-thumb); border-radius:99px;}
.kb-msgs::-webkit-scrollbar-track{background:transparent;}

.kb-m{display:flex; gap:.5rem; max-width:100%;}
/* A question is short, so its bubble hangs off the baseline. An answer can run
   long, so its avatar tracks the top of the bubble instead of drifting down. */
.kb-m.kb-me{justify-content:flex-end; align-items:flex-end;}
.kb-m.kb-bot{align-items:flex-start;}
.kb-m .kb-av{
  width:26px; height:26px; border-radius:8px; flex:none; display:grid; place-items:center;
  font-size:.72rem; color:#04231A; margin-top:3px;
  background:linear-gradient(140deg,var(--jade),var(--violet));
  box-shadow:0 4px 12px -5px rgba(0,229,160,.7);
}
.kb-bub{
  position:relative; min-width:0; max-width:88%;
  padding:.6rem .78rem; border-radius:14px;
  font-size:.82rem; line-height:1.58; color:var(--body);
  border:1px solid var(--border); background:var(--surface-3);
  box-shadow:0 8px 22px -14px rgba(0,0,0,.7);
  overflow-wrap:anywhere;
}
.kb-me .kb-bub{
  background:linear-gradient(135deg,var(--jade-soft),var(--violet-soft));
  border-color:var(--jade-line); color:var(--text); border-bottom-right-radius:5px;
  animation:kbSendIn .46s cubic-bezier(.16,1.5,.4,1) both;
}
.kb-bot .kb-bub{border-bottom-left-radius:5px;
  animation:kbRecvIn .5s cubic-bezier(.16,1.44,.4,1) both;}
.kb-bot .kb-av{animation:kbAvIn .42s cubic-bezier(.16,1.6,.4,1) both;}
@keyframes kbSendIn{
  0%{opacity:0; transform:translate(18px,10px) scale(.8);}
  100%{opacity:1; transform:translate(0,0) scale(1);}
}
@keyframes kbRecvIn{
  0%{opacity:0; transform:translate(-14px,12px) scale(.82);}
  100%{opacity:1; transform:translate(0,0) scale(1);}
}
@keyframes kbAvIn{
  0%{opacity:0; transform:scale(.3) rotate(-40deg);}
  100%{opacity:1; transform:scale(1) rotate(0);}
}

/* Typing indicator — three dots on a staggered bounce */
.kb-typing{display:flex; gap:.32rem; align-items:center; padding:.72rem .85rem;}
.kb-typing i{
  width:7px; height:7px; border-radius:50%; background:var(--jade);
  animation:kbDot 1.15s cubic-bezier(.3,.7,.4,1) infinite;
}
.kb-typing i:nth-child(2){animation-delay:.14s; background:var(--violet);}
.kb-typing i:nth-child(3){animation-delay:.28s; background:var(--amber);}
@keyframes kbDot{
  0%,70%,100%{transform:translateY(0) scale(1); opacity:.45;}
  32%{transform:translateY(-8px) scale(1.28); opacity:1;}
}

/* ═══ ANSWER TYPOGRAPHY ═════════════════════════════════════════════════ */
.kb-a p{font-size:.82rem !important; line-height:1.6; margin:0 0 .45rem !important;
  color:var(--body) !important;}
.kb-a p:last-child{margin-bottom:0 !important;}
.kb-a b{color:var(--strong); font-weight:750;}
.kb-a code{
  font-family:var(--mono); font-size:.72rem; padding:.06rem .34rem; border-radius:5px;
  background:var(--flat-soft); border:1px solid var(--border); color:var(--jade-text);
}
.kb-a .kb-note{
  font-size:.73rem !important; color:var(--faint) !important; line-height:1.5;
  padding-left:.6rem; border-left:2px solid var(--border-strong); margin-top:.5rem !important;
}
.kb-a .kb-scope{
  margin-top:.6rem; padding:.34rem .55rem; border-radius:7px;
  font-family:var(--mono); font-size:.64rem; letter-spacing:.02em;
  color:var(--faint); background:var(--flat-soft); border:1px dashed var(--dashed);
  overflow-wrap:anywhere;
}
.kb-a .kb-big{
  font-family:var(--mono); font-size:1.85rem; font-weight:700; letter-spacing:-.03em;
  line-height:1.15; margin:.15rem 0 .5rem; color:var(--text);
  background:var(--hero-title); -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent;
  animation:kbRise .55s cubic-bezier(.16,1.4,.4,1) both;
}
@keyframes kbRise{0%{opacity:0; transform:translateY(10px) scale(.94);}
  100%{opacity:1; transform:translateY(0) scale(1);}}

.kb-a .kb-ul{margin:.15rem 0 .35rem; padding-left:.05rem; list-style:none;}
.kb-a .kb-ul li{
  position:relative; padding-left:.9rem; margin-bottom:.34rem;
  font-size:.8rem; line-height:1.55; color:var(--body);
  animation:kbSlide .42s cubic-bezier(.2,.9,.3,1) both;
  animation-delay:calc(var(--i,0) * 55ms + 120ms);
}
.kb-a .kb-ul li::before{
  content:""; position:absolute; left:.05rem; top:.52rem;
  width:5px; height:5px; border-radius:50%;
  background:linear-gradient(135deg,var(--jade),var(--violet));
}
@keyframes kbSlide{0%{opacity:0; transform:translateX(-10px);}
  100%{opacity:1; transform:translateX(0);}}

/* Label / value grid */
.kb-a .kb-kvs{
  display:grid; grid-template-columns:1fr 1fr; gap:.3rem; margin:.35rem 0 .5rem;
}
.kb-a .kb-kv{
  display:flex; flex-direction:column; gap:.1rem;
  padding:.42rem .55rem; border-radius:9px;
  background:var(--flat-soft); border:1px solid var(--border);
  animation:kbPopIn .44s cubic-bezier(.16,1.5,.4,1) both;
  animation-delay:calc(var(--i,0) * 48ms + 100ms);
  transition:border-color .2s, transform .2s;
}
.kb-a .kb-kv:hover{border-color:var(--jade-line); transform:translateY(-2px);}
.kb-a .kb-kv span{font-size:.6rem; font-weight:800; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted);}
.kb-a .kb-kv b{font-family:var(--mono); font-size:.87rem; font-weight:700;
  color:var(--text); letter-spacing:-.02em;}
@keyframes kbPopIn{0%{opacity:0; transform:translateY(9px) scale(.9);}
  100%{opacity:1; transform:translateY(0) scale(1);}}

/* Ranked bars */
.kb-a .kb-rank{display:flex; flex-direction:column; gap:.26rem; margin:.35rem 0 .5rem;}
.kb-a .kb-row{
  position:relative; display:flex; align-items:center; gap:.45rem;
  padding:.36rem .5rem; border-radius:8px; overflow:hidden;
  background:var(--flat-soft); border:1px solid var(--border);
  animation:kbPopIn .44s cubic-bezier(.16,1.5,.4,1) both;
  animation-delay:calc(var(--i,0) * 62ms + 130ms);
}
/* The fill holds its colour to 78% of its own width and then fades out. A hard
   right edge would read as a strike-through wherever it crossed a long label. */
.kb-a .kb-row > i{
  position:absolute; left:0; top:0; bottom:0; width:var(--w,0%); z-index:0;
  background:linear-gradient(90deg,var(--jade-soft) 0%,var(--jade-soft) 78%,transparent 100%);
  animation:kbGrow .85s cubic-bezier(.2,.9,.25,1) both;
  animation-delay:calc(var(--i,0) * 62ms + 200ms);
}
.kb-a .kb-amber .kb-row > i{background:linear-gradient(90deg,var(--amber-soft) 0%,var(--amber-soft) 78%,transparent 100%);}
.kb-a .kb-rose .kb-row > i{background:linear-gradient(90deg,var(--rose-soft) 0%,var(--rose-soft) 78%,transparent 100%);}
.kb-a .kb-violet .kb-row > i{background:linear-gradient(90deg,var(--violet-soft) 0%,var(--violet-soft) 78%,transparent 100%);}
.kb-a .kb-teal .kb-row > i{background:linear-gradient(90deg,var(--jade-soft) 0%,var(--jade-soft) 78%,transparent 100%);}
@keyframes kbGrow{0%{width:0;}100%{width:var(--w,0%);}}
.kb-a .kb-rk{
  position:relative; z-index:1; flex:none;
  width:16px; height:16px; border-radius:5px; display:grid; place-items:center;
  font-family:var(--mono); font-size:.6rem; font-weight:700;
  color:var(--muted); background:var(--surface-3); border:1px solid var(--border);
}
.kb-a .kb-lb{
  position:relative; z-index:1; flex:1 1 auto; min-width:0;
  font-size:.76rem; font-weight:600; color:var(--text);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.kb-a .kb-vl{
  position:relative; z-index:1; flex:none;
  font-family:var(--mono); font-size:.74rem; font-weight:700; color:var(--text);
  letter-spacing:-.02em;
}

/* Delta chips */
.kb-a .kb-tag{
  display:inline-flex; align-items:center; gap:.25rem;
  font-family:var(--mono); font-size:.7rem; font-weight:700;
  padding:.14rem .42rem; border-radius:6px;
  background:var(--flat-soft); color:var(--muted);
}
.kb-a .kb-tag em{font-style:normal; font-weight:500; opacity:.75;}
.kb-a .kb-tag.kb-up{color:var(--jade-text); background:var(--jade-soft);}
.kb-a .kb-tag.kb-down{color:var(--rose-text); background:var(--rose-soft);}
.kb-a .kb-tag.kb-flat{color:var(--muted); background:var(--flat-soft);}
.kb-a .kb-mvs{display:flex; flex-wrap:wrap; gap:.3rem; margin:.2rem 0 .5rem;}
.kb-a .kb-mv{
  display:inline-flex; align-items:center; gap:.34rem;
  padding:.24rem .45rem; border-radius:8px;
  font-size:.68rem; font-weight:700; color:var(--muted);
  background:var(--flat-soft); border:1px solid var(--border);
  animation:kbPopIn .4s cubic-bezier(.16,1.5,.4,1) both;
}
.kb-a .kb-chiplbl{
  font-size:.58rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase;
  color:var(--jade-text); background:var(--jade-soft); border:1px solid var(--jade-line);
  padding:.08rem .36rem; border-radius:99px; margin-left:.25rem; white-space:nowrap;
}

/* Definition blocks */
.kb-a .kb-def{
  display:flex; flex-direction:column; gap:.2rem;
  padding:.5rem .6rem; border-radius:10px; margin-bottom:.34rem;
  background:var(--flat-soft); border:1px solid var(--border);
  border-left:2px solid var(--jade);
  animation:kbSlide .44s cubic-bezier(.2,.9,.3,1) both;
  animation-delay:calc(var(--i,0) * 60ms + 110ms);
}
.kb-a .kb-def b{font-size:.78rem; color:var(--text);}
.kb-a .kb-def code{align-self:flex-start; font-size:.68rem;}
.kb-a .kb-def span{font-size:.72rem; color:var(--faint); line-height:1.5;}

/* Comparison table */
.kb-a .kb-tbl{overflow-x:auto; margin:.35rem 0 .5rem;}
.kb-a .kb-tbl table{border-collapse:separate; border-spacing:0 .18rem; width:100%;}
.kb-a .kb-tbl th{
  font-size:.6rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase;
  color:var(--muted); text-align:right; padding:.2rem .42rem; white-space:nowrap;
}
.kb-a .kb-tbl tr > th:first-child{text-align:left;}
.kb-a .kb-tbl td{
  font-family:var(--mono); font-size:.74rem; font-weight:600; color:var(--body);
  text-align:right; padding:.32rem .42rem; white-space:nowrap;
  background:var(--flat-soft); border-top:1px solid var(--border);
  border-bottom:1px solid var(--border);
}
.kb-a .kb-tbl tr{animation:kbSlide .42s cubic-bezier(.2,.9,.3,1) both;
  animation-delay:calc(var(--i,0) * 55ms + 120ms);}
.kb-a .kb-tbl td.kb-best{
  color:var(--jade-text); background:var(--jade-soft);
  border-color:var(--jade-line); font-weight:750;
}

/* ═══ SUGGESTION CHIPS ══════════════════════════════════════════════════ */
.kb-chips-lbl{
  font-size:.58rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase;
  color:var(--faint); margin:.35rem 0 .1rem; display:flex; align-items:center; gap:.4rem;
}
.kb-chips-lbl::after{content:""; flex:1; height:1px;
  background:linear-gradient(90deg,var(--border-strong),transparent);}
[class*="st-key-kb_chip_"] button{
  width:100% !important; min-height:0 !important;
  padding:.34rem .6rem !important; border-radius:99px !important;
  justify-content:flex-start !important;
  background:var(--flat-soft) !important; border:1px dashed var(--border-strong) !important;
  transition:all .2s cubic-bezier(.2,.9,.3,1.3);
  animation:kbChipIn .5s cubic-bezier(.16,1.5,.4,1) both;
}
[class*="st-key-kb_chip_0"] button{animation-delay:.06s;}
[class*="st-key-kb_chip_1"] button{animation-delay:.14s;}
[class*="st-key-kb_chip_2"] button{animation-delay:.22s;}
[class*="st-key-kb_chip_3"] button{animation-delay:.30s;}
[class*="st-key-kb_chip_"] button p{
  font-size:.73rem !important; font-weight:600 !important; color:var(--muted) !important;
  margin:0 !important; text-align:left;
}
[class*="st-key-kb_chip_"] button:hover{
  background:var(--jade-soft) !important; border-style:solid !important;
  border-color:var(--jade-line) !important;
  transform:translateX(4px) scale(1.015);
}
[class*="st-key-kb_chip_"] button:hover p{color:var(--jade-text) !important;}
@keyframes kbChipIn{
  0%{opacity:0; transform:translateX(-14px) scale(.9);}
  100%{opacity:1; transform:translateX(0) scale(1);}
}

/* ═══ INPUT ═════════════════════════════════════════════════════════════ */
.st-key-kb_panel [data-testid="stChatInput"],
.st-key-kb_panel [data-testid="stChatInputContainer"]{
  background:var(--input-bg) !important;
  border:1px solid var(--border-strong) !important;
  border-radius:14px !important;
  transition:border-color .22s ease, box-shadow .22s ease;
}
.st-key-kb_panel [data-testid="stChatInput"]:focus-within,
.st-key-kb_panel [data-testid="stChatInputContainer"]:focus-within{
  border-color:var(--jade) !important;
  box-shadow:0 0 0 3px var(--jade-soft) !important;
}
.st-key-kb_panel [data-testid="stChatInput"] textarea{
  font-size:.82rem !important; color:var(--text) !important;
  background:transparent !important;
}
.st-key-kb_panel [data-testid="stChatInput"] textarea::placeholder{
  color:var(--faint) !important; opacity:1;
}
.st-key-kb_panel [data-testid="stChatInputSubmitButton"]{
  background:var(--primary-bg) !important; border-radius:9px !important;
  transition:transform .18s cubic-bezier(.2,.9,.3,1.5);
}
.st-key-kb_panel [data-testid="stChatInputSubmitButton"]:hover{transform:scale(1.14);}
.st-key-kb_panel [data-testid="stChatInputSubmitButton"] svg{fill:var(--primary-text) !important;}
.st-key-kb_panel [data-testid="stChatInputSubmitButton"]:disabled{background:var(--flat-soft) !important;}
.st-key-kb_panel [data-testid="stChatInputSubmitButton"]:disabled svg{fill:var(--faint) !important;}
.kb-foot{
  font-size:.6rem; color:var(--faint); text-align:center;
  margin:.15rem 0 .1rem; letter-spacing:.02em;
}

/* ═══ SMALL SCREENS ═════════════════════════════════════════════════════ */
@media (max-width:640px){
  .st-key-kb_panel{
    left:.6rem; right:.6rem; top:3.9rem;
    width:auto !important; max-width:none;
  }
  .st-key-kb_dock{right:3.6rem; top:.38rem;}
}

/* ═══ REDUCED MOTION ════════════════════════════════════════════════════ */
@media (prefers-reduced-motion:reduce){
  .st-key-kb_dock::before, .st-key-kb_dock::after,
  .st-key-kb_dock button, .st-key-kb_dock .stButton::before,
  .st-key-kb_toggle_off button::after, .st-key-kb_panel, .st-key-kb_panel::before,
  .kb-head .kb-orb, .kb-head .kb-who i, .kb-me .kb-bub, .kb-bot .kb-bub,
  .kb-bot .kb-av, .kb-typing i, .kb-a .kb-big, .kb-a .kb-ul li, .kb-a .kb-kv,
  .kb-a .kb-row, .kb-a .kb-row > i, .kb-a .kb-def, .kb-a .kb-tbl tr,
  .kb-a .kb-mv, [class*="st-key-kb_chip_"] button{
    animation:none !important;
  }
  .kb-a .kb-row > i{width:var(--w,0%);}
}
"""


def _css() -> str:
    body = " ".join(l.strip() for l in _CSS_BODY.splitlines() if l.strip())
    return f"<style>{body}</style>"


# ═════════════════════════════════════════════════════════════════════════════
# STATE
# ═════════════════════════════════════════════════════════════════════════════
def _init() -> None:
    st.session_state.setdefault("kb_open", False)
    st.session_state.setdefault("kb_msgs", [])
    st.session_state.setdefault("kb_pending", None)
    st.session_state.setdefault("kb_thinking", False)


def _toggle() -> None:
    st.session_state.kb_open = not st.session_state.kb_open


def _close() -> None:
    st.session_state.kb_open = False


def _clear() -> None:
    st.session_state.kb_msgs = []
    st.session_state.kb_pending = None
    st.session_state.kb_thinking = False


def _ask(text: str) -> None:
    text = str(text).strip()
    if not text:
        return
    st.session_state.kb_open = True
    st.session_state.kb_msgs.append({"role": "user", "text": text})
    st.session_state.kb_pending = text
    st.session_state.kb_thinking = False


def reset() -> None:
    """Drop the conversation. Called when a session ends or a new file loads."""
    for key in ("kb_open", "kb_msgs", "kb_pending", "kb_thinking"):
        st.session_state.pop(key, None)


# ═════════════════════════════════════════════════════════════════════════════
# RENDERING
# ═════════════════════════════════════════════════════════════════════════════
def _messages_html(msgs: list[dict], thinking: bool) -> str:
    items: list[str] = []
    for m in msgs:
        if m["role"] == "user":
            items.append('<div class="kb-m kb-me"><div class="kb-bub">'
                         f'{escape(m["text"])}</div></div>')
        else:
            items.append('<div class="kb-m kb-bot"><div class="kb-av">◈</div>'
                         f'<div class="kb-bub kb-a">{m["html"]}</div></div>')
    if thinking:
        items.append('<div class="kb-m kb-bot"><div class="kb-av">◈</div>'
                     '<div class="kb-bub kb-typing"><i></i><i></i><i></i></div></div>')
    # column-reverse in CSS, so the newest bubble is emitted first and lands
    # at the bottom with the scroller already parked there.
    return '<div class="kb-msgs">' + "".join(reversed(items)) + "</div>"


def _panel(ctx: dict, thinking: bool) -> None:
    with st.container(key="kb_panel"):
        head, c_clear, c_close = st.columns([1, .15, .15], vertical_alignment="center")
        with head:
            st.html('<div class="kb-head"><div class="kb-orb">◈</div>'
                    '<div class="kb-who"><b>Analytics Assistant</b>'
                    '<span><i></i>Reading the live dataset</span></div></div>')
        with c_clear:
            st.button("⟲", key="kb_clear", on_click=_clear,
                      help="Start a fresh conversation")
        with c_close:
            st.button("✕", key="kb_close", on_click=_close, help="Close the assistant")

        msgs = st.session_state.kb_msgs
        st.html(_messages_html(msgs, thinking))

        chips: list[str] = []
        if not thinking:
            for m in reversed(msgs):
                if m["role"] == "bot":
                    chips = list(m.get("chips") or [])
                    break
        if chips:
            st.html('<div class="kb-chips-lbl">Try next</div>')
            for i, chip in enumerate(chips[:MAX_CHIPS]):
                st.button(chip, key=f"kb_chip_{i}", on_click=_ask, args=(chip,),
                          width="stretch")

        prompt = st.chat_input("Ask anything about this dashboard…", key="kb_input")
        st.html('<div class="kb-foot">Answers are computed from the loaded workbook, '
                "not generated.</div>")
        if prompt:
            _ask(prompt)
            st.rerun()


def render(ctx: dict) -> None:
    """
    Draw the assistant dock. Call once per script run, after the main layout.

    ``ctx`` is passed straight to :func:`assistant.answer` and needs:
    ``df``, ``fdf``, ``sel``, ``bid_range``, ``source_label``, ``theme_mode``
    and optionally ``quality_fn``.
    """
    _init()
    st.html(_css())

    # Answer a question raised on the previous run.
    if st.session_state.kb_pending and st.session_state.kb_thinking:
        reply = assistant.answer(st.session_state.kb_pending, ctx)
        st.session_state.kb_msgs.append(
            {"role": "bot", "html": reply.html, "chips": reply.chips})
        st.session_state.kb_pending = None
        st.session_state.kb_thinking = False

    thinking = bool(st.session_state.kb_pending)
    if thinking:
        st.session_state.kb_thinking = True

    open_now = bool(st.session_state.kb_open)
    with st.container(key="kb_dock"):
        st.button("✕" if open_now else "✦",
                  key="kb_toggle_on" if open_now else "kb_toggle_off",
                  on_click=_toggle,
                  help="Close the assistant" if open_now
                       else "Ask the assistant about this dashboard")

    if open_now:
        if not st.session_state.kb_msgs:
            opening = assistant.opening_message(ctx)
            st.session_state.kb_msgs.append(
                {"role": "bot", "html": opening.html, "chips": opening.chips})
        _panel(ctx, thinking)

    # The typing bubble is on screen by now; pause on it, then answer.
    if thinking:
        time.sleep(_THINK_PAUSE)
        st.rerun()
