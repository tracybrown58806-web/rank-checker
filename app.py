import os
import time
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

SERPER_URL = "https://google.serper.dev/search"

st.set_page_config(page_title="Keyword Rank Checker", page_icon="📈", layout="wide")
st.title("📈 Keyword Rank Checker")
st.caption("Keywords dalein, apna domain dalein, aur Google mein current ranking dekhein.")


def clean_domain(value: str) -> str:
    """'https://www.example.com/page' -> 'example.com'"""
    value = value.strip().lower()
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    host = urlparse(value).netloc
    return host[4:] if host.startswith("www.") else host


def matches_domain(url: str, domain: str) -> bool:
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return host == domain or host.endswith("." + domain)


def check_rank(api_key, keyword, domain, country, language, location, depth):
    payload = {"q": keyword, "gl": country, "hl": language, "num": depth}
    if location:
        payload["location"] = location
    resp = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    organic = resp.json().get("organic", [])
    for item in organic:
        if matches_domain(item.get("link", ""), domain):
            return item.get("position"), item.get("link"), item.get("title")
    return None, None, None


# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "Serper.dev API Key",
        value=os.environ.get("SERPER_API_KEY", ""),
        type="password",
        help="serper.dev par free account bana kar key milti hai.",
    )
    country = st.text_input("Country code (gl)", value="pk", help="Jaise pk, us, gb, ae, in")
    language = st.text_input("Language (hl)", value="en", help="Jaise en, ur")
    location = st.text_input(
        "City / Location (optional)",
        value="",
        placeholder="Karachi, Sindh, Pakistan",
        help="Local ranking check karne ke liye.",
    )
    depth = st.selectbox(
        "Kitne results tak check karein", [10, 20, 50, 100], index=3,
        help="Zyada depth par zyada API credits lag sakte hain. Serper ki pricing check kar lein.",
    )
    delay = st.slider("Requests ke beech delay (seconds)", 0.0, 2.0, 0.3, 0.1)

# ---------------- Main ----------------
domain_input = st.text_input("Aap ka domain", placeholder="example.com")
keywords_input = st.text_area(
    "Keywords (har line mein ek)", height=200, placeholder="best laptop in pakistan\nseo services karachi"
)

if st.button("Check Rankings", type="primary"):
    keywords = [k.strip() for k in keywords_input.splitlines() if k.strip()]
    keywords = list(dict.fromkeys(keywords))  # duplicates hata do

    if not api_key:
        st.error("Sidebar mein API key dalein.")
    elif not domain_input.strip():
        st.error("Domain dalein.")
    elif not keywords:
        st.error("Kam az kam ek keyword dalein.")
    else:
        domain = clean_domain(domain_input)
        rows = []
        progress = st.progress(0.0, text="Shuru ho raha hai...")

        for i, kw in enumerate(keywords, start=1):
            try:
                pos, url, title = check_rank(api_key, kw, domain, country, language, location, depth)
                rows.append({
                    "Keyword": kw,
                    "Rank": pos if pos else f"Top {depth} mein nahi",
                    "URL": url or "",
                    "Title": title or "",
                })
            except requests.HTTPError as e:
                code = e.response.status_code
                msg = "API key ghalat hai" if code in (401, 403) else (
                    "Credits khatam ya limit" if code == 429 else f"HTTP error {code}")
                rows.append({"Keyword": kw, "Rank": f"Error: {msg}", "URL": "", "Title": ""})
            except Exception as e:
                rows.append({"Keyword": kw, "Rank": f"Error: {e}", "URL": "", "Title": ""})

            progress.progress(i / len(keywords), text=f"{i}/{len(keywords)}: {kw}")
            time.sleep(delay)

        progress.empty()
        df = pd.DataFrame(rows)

        ranked = pd.to_numeric(df["Rank"], errors="coerce").dropna()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total keywords", len(df))
        c2.metric("Ranking mein", len(ranked))
        c3.metric("Average rank", f"{ranked.mean():.1f}" if len(ranked) else "-")

        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "CSV download karein",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"rankings_{domain}_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
