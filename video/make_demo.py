"""Builds demo.mp4 (<3 min): real screen footage of the running app + voice-over + captions + animated title cards.

Needs: the app running on http://127.0.0.1:8765, Playwright (uses installed Edge), ffmpeg/ffprobe on PATH, Windows (SAPI voice).
Run:  python video/make_demo.py
"""
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
APP = "http://127.0.0.1:8765/"
GAP = 0.7  # seconds of silence after each narration clip

CARD_CSS = """<style>
*{box-sizing:border-box}body{margin:0;height:100vh;background:#0f1624;color:#eef2f8;font-family:Segoe UI,system-ui,sans-serif;display:flex;flex-direction:column;justify-content:center;padding:0 110px;overflow:hidden}
h1{font-size:76px;margin:0;animation:in 1s ease both}h1 span{color:#f5c542}
p.s{font-size:30px;color:#a3b0c4;margin:18px 0 0;animation:in 1s .5s ease both}
ul{list-style:none;padding:0;margin:34px 0 0}li{font-size:34px;margin:14px 0;opacity:0;animation:in .8s ease both}
li:nth-child(1){animation-delay:1.6s}li:nth-child(2){animation-delay:3.6s}li:nth-child(3){animation-delay:5.6s}li b{color:#f5c542}
.bar{position:absolute;left:0;bottom:0;height:8px;background:#f5c542;animation:grow 12s linear both}
@keyframes in{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}@keyframes grow{from{width:0}to{width:100%}}
</style>"""

TITLE = CARD_CSS + """<h1>Freelance<span>Ledger</span></h1><p class="s">Built for the PayPal AI Hackathon</p>
<ul><li>1. Convert every payment to <b>INR</b></li><li>2. Watch the <b>GST registration threshold</b></li><li>3. Keep your <b>e-FIRA / FIRC</b> paperwork in order</li></ul><div class="bar"></div>"""

OUTRO = CARD_CSS + """<h1>Open source. <span>MIT.</span></h1><p class="s">PayPal sandbox + Gemini + AG Grid</p>
<ul><li>Runs without any AI key (rule-based fallback)</li><li>Record-keeping only, <b>not tax advice</b></li><li>github.com/Spooke02/freelance-ledger</li></ul><div class="bar"></div>"""

CURSOR_JS = """(() => { const d = document.createElement('div');
d.style.cssText='position:fixed;z-index:99999;width:22px;height:22px;border-radius:50%;background:rgba(245,197,66,.85);border:2px solid #fff;pointer-events:none;left:-50px;top:-50px;transition:left .05s,top .05s';
document.addEventListener('DOMContentLoaded',()=>document.body.appendChild(d));
document.addEventListener('mousemove',e=>{d.style.left=(e.clientX-11)+'px';d.style.top=(e.clientY-11)+'px'}); })();"""

SCENES = [
    ("title", "FreelanceLedger. Indian freelancers who are paid through PayPal in dollars face three chores every month. "
              "Convert each payment to rupees. Watch the GST registration threshold. And keep the foreign remittance paperwork, the e-FIRA, in order. "
              "FreelanceLedger does this from your PayPal payments."),
    ("paypal", "The app connects to the PayPal sandbox using OAuth. This payment was created through the Orders API and read back with Transaction Search. "
               "It is converted to rupees at the European Central Bank rate for the payment date, and the PayPal fee is tracked separately. No real money moves."),
    ("demo", "Here is a fuller year of fictional sample data. The cards show gross income, fees, and progress toward the twenty lakh rupee GST registration threshold, "
             "with a warning level as the freelancer gets closer."),
    ("grid", "Every payment is listed in an AG Grid table that you can sort and filter. Tick the box when you hold the e-FIRA for a payment, "
             "and the count of missing paperwork updates straight away."),
    ("ai", "Gemini categorises each payment and explains the position in plain language. You can also ask questions about your own ledger. "
           "Here I ask which payments still need paperwork and which client paid the most."),
    ("outro", "FreelanceLedger is open source under the MIT licence, and it has automated tests. It also runs without any AI key, using a rule-based fallback. "
              "It is record-keeping, not tax advice. Thank you for watching."),
]


PIPER_VOICE = HERE / "voices" / "en_US-lessac-medium.onnx"  # neural voice (offline); falls back to the Windows voice if missing


def tts(text: str, path: Path) -> float:
    txt = path.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    if PIPER_VOICE.exists():
        subprocess.run([sys.executable, "-m", "piper", "-m", str(PIPER_VOICE), "-f", str(path), "--length-scale", "1.08", "--sentence-silence", "0.35"],
                       input=text.encode("utf-8"), check=True, capture_output=True)
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    ps = (f"Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SelectVoice('Microsoft Zira Desktop'); "
          f"$s.Rate=0; $s.SetOutputToWaveFile('{path}'); $s.Speak([IO.File]::ReadAllText('{txt}',[Text.Encoding]::UTF8)); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def concat_audio(clips: list[Path], durs: list[float], out: Path) -> None:
    """Concatenate narration; pad each clip with silence up to its scene duration."""
    with wave.open(str(clips[0])) as w0:
        params = w0.getparams()
    with wave.open(str(out), "wb") as o:
        o.setparams(params)
        for c, d in zip(clips, durs):
            with wave.open(str(c)) as w:
                o.writeframes(w.readframes(w.getnframes()))
                pad = max(0.0, d - w.getnframes() / w.getframerate())
            o.writeframes(b"\x00" * int(params.framerate * pad) * params.sampwidth * params.nchannels)


def srt_time(t: float) -> str:
    return f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(t % 1 * 1000):03}"


def make_srt(texts: list[str], durs: list[float], path: Path, extras: list[float] | None = None) -> None:
    import re
    lines, t, n = [], 0.0, 1
    for text, d, extra in zip(texts, durs, extras or [0.0] * len(texts)):
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        total = sum(len(p) for p in parts)
        cur = t
        for p in parts:
            span = d * len(p) / total
            lines.append(f"{n}\n{srt_time(cur)} --> {srt_time(cur + span)}\n{p}\n")
            cur += span
            n += 1
        t += d + GAP + extra
    path.write_text("\n".join(lines), encoding="utf-8")


def wait_until(start: float, seconds: float, page) -> None:
    left = seconds - (time.monotonic() - start)
    if left > 0:
        page.wait_for_timeout(int(left * 1000))


def move_click(page, selector: str) -> None:
    box = page.locator(selector).first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25)
    page.wait_for_timeout(250)
    page.mouse.down(); page.mouse.up()


def ready(page, text: str | None = None) -> None:
    page.wait_for_function("document.getElementById('msg').textContent === '' && document.querySelectorAll('.ag-row').length > 0", timeout=60000)
    if text:
        page.wait_for_function("t => document.body.innerText.includes(t)", arg=text, timeout=60000)
    page.wait_for_timeout(800)


def run_scene(page, name: str, dur: float) -> None:
    start = time.monotonic()
    if name in ("title", "outro"):
        page.set_content(TITLE if name == "title" else OUTRO)
    elif name == "paypal":
        page.goto(APP); ready(page)
        page.select_option("#src", "paypal"); page.wait_for_timeout(500); ready(page, "John Doe")
        page.mouse.move(700, 330, steps=30)
    elif name == "demo":
        page.select_option("#src", "demo"); page.wait_for_timeout(500); ready(page, "Northwind")
        page.mouse.move(300, 120, steps=30); page.wait_for_timeout(1200); page.mouse.move(640, 150, steps=30)
    elif name == "grid":
        page.mouse.move(300, 420, steps=30)
        move_click(page, ".ag-header-cell[col-id='gross_inr'] .ag-header-cell-label"); page.wait_for_timeout(1200)
        move_click(page, ".ag-row[row-index='0'] input[type=checkbox]"); page.wait_for_timeout(1500)
        move_click(page, ".ag-row[row-index='1'] input[type=checkbox]")
    elif name == "ai":
        page.locator("#q").scroll_into_view_if_needed()
        move_click(page, "#q")
        page.keyboard.type("Which payments still need an e-FIRA, and which client paid the most?", delay=45)
        page.wait_for_timeout(500)
        move_click(page, "#askbtn")
        page.wait_for_function("document.getElementById('ans').textContent && document.getElementById('ans').textContent !== 'Thinking...'", timeout=60000)
    wait_until(start, dur, page)


def main() -> None:
    clips, durs = [], []
    for i, (name, text) in enumerate(SCENES):
        p = OUT / f"n{i}.wav"
        d = tts(text, p)
        clips.append(p); durs.append(d + GAP + (5.0 if name == "ai" else 0.0))  # hold on the AI answer
        print(f"scene {name}: {d:.1f}s narration")
    audio = OUT / "narration.wav"
    concat_audio(clips, durs, audio)
    make_srt([t for _, t in SCENES], [d - GAP - (5.0 if n == 'ai' else 0.0) for (n, _), d in zip(SCENES, durs)], OUT / "subs.srt", [5.0 if n == 'ai' else 0.0 for n, _ in SCENES])
    total = sum(durs)
    print(f"total {total:.1f}s")
    assert total < 175, "video must stay under 3 minutes"

    import urllib.request  # warm the server's AI cache so scenes show data immediately
    for src in ("paypal", "demo"):
        urllib.request.urlopen(f"{APP}api/state?source={src}", timeout=120).read()
    vdir = OUT / "rec"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(vdir), record_video_size={"width": 1280, "height": 720})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        t0 = time.monotonic()
        for (name, _), d in zip(SCENES, durs):
            a = time.monotonic(); run_scene(page, name, d)
            print(f"  {name}: took {time.monotonic() - a:.1f}s (budget {d:.1f}s), at {time.monotonic() - t0:.1f}s")
        page.close(); ctx.close(); browser.close()
    webm = max(vdir.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-i", str(audio),
                    "-vf", "tpad=stop_mode=clone:stop_duration=15,subtitles=out/subs.srt:force_style='FontName=Segoe UI,FontSize=11,BorderStyle=3,Outline=1,Shadow=0,MarginV=14,PrimaryColour=&HFFFFFF&,BackColour=&H99000000&'",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest", str(HERE / "demo.mp4")],
                   check=True, cwd=HERE)
    print("wrote", HERE / "demo.mp4")


if __name__ == "__main__":
    main()
