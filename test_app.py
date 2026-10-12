import os, tempfile
os.environ["WORLDPULSE_DEMO"] = "1"
os.environ["WORLDPULSE_TEST"] = "1"
os.environ["WORLDPULSE_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from streamlit.testing.v1 import AppTest
APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")

def run(at):
    at.run(timeout=60)
    assert not at.exception, [e.value for e in at.exception]
    return at

def test_pages_and_flows():
    at = run(AppTest.from_file(APP))
    assert at.title[0].value == "Live news"
    md = " ".join(m.value for m in at.markdown)
    assert "OPEC" in md and "Impact:" in md
    # track first story, then read it
    track = [b for b in at.button if b.label == "☆ Track"][0]; track.click(); run(at)
    read = [b for b in at.button if b.label == "Read"][0]; read.click(); run(at)
    assert at.session_state["page"] == "Reader"
    assert any("Market impact" == h.value for h in at.subheader)
    # filters
    at.session_state["page"] = "Live news"; run(at)
    at.text_input(key="q").input("RBI"); run(at)
    assert any("RBI" in m.value for m in at.markdown)
    # other pages
    for p in ["Markets", "My tracker", "Sources & settings", "Reader"]:
        at.session_state["page"] = p; run(at)
    at.session_state["page"] = "My tracker"; run(at)
    assert any(m.label == "Stories tracked" and m.value == "1" for m in at.metric)
