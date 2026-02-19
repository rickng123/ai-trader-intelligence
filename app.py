import streamlit as st
import yfinance as yf
import requests
import feedparser  # Run: pip install feedparser
from bs4 import BeautifulSoup
from openai import OpenAI

# --- 1. CONFIG & AUTH ---
st.set_page_config(page_title="AI Trader Intelligence", layout="wide", page_icon="📈")

with st.sidebar:
    st.header("Authentication")
    user_api_key = st.text_input("OpenAI API Key", type="password", help="Enter your sk-... key here")
    st.info("The news section now uses a fallback RSS engine if yfinance is blocked.")

# Initialize OpenAI client only if key is provided
client = OpenAI(api_key=user_api_key) if user_api_key else None
SEC_HEADERS = {"User-Agent": "TraderResearch yourname@example.com"}

# --- 2. THE ENGINES ---
@st.cache_data
def get_cik_map():
    url = "https://www.sec.gov/files/company_tickers.json"
    response = requests.get(url, headers=SEC_HEADERS)
    return {v['ticker']: str(v['cik_str']).zfill(10) for k, v in response.json().items()}

def get_filing_text(url):
    try:
        response = requests.get(url, headers=SEC_HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        for tag in soup(["script", "style"]):
            tag.decompose()
        return ' '.join(soup.get_text(separator=' ').splitlines())[:12000] 
    except:
        return "Extraction failed."

def get_ticker_news(ticker):
    """Fetches news from yfinance with a robust Google News RSS fallback."""
    # Try yfinance first
    stock = yf.Ticker(ticker)
    try:
        y_news = stock.news
        if y_news and len(y_news) > 0:
            return [{'title': n['title'], 'link': n['link'], 'source': n.get('publisher', 'Yahoo')} for n in y_news]
    except:
        pass
    
    # Fallback: Google News RSS
    rss_url = f"https://news.google.com/rss/search?q={ticker}+stock+news&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    return [{'title': e.title, 'link': e.link, 'source': e.source.get('title', 'Google News')} for e in feed.entries[:10]]

# --- 3. UI LAYOUT ---
ticker = st.sidebar.text_input("Ticker Symbol", value="NVDA").upper()

if ticker:
    st.title(f"🚀 {ticker} Intelligence Terminal")
    cik_map = get_cik_map()
    cik_id = cik_map.get(ticker)
    
    col_news, col_filings = st.columns([1, 1.5], gap="large")

    # LEFT COLUMN: NEWS
    with col_news:
        st.subheader("📰 Latest Market News")
        items = get_ticker_news(ticker)
        if not items:
            st.warning("No news found for this ticker.")
        else:
            for item in items:
                with st.expander(item['title']):
                    st.caption(f"Source: {item['source']}")
                    st.markdown(f"[Read Full Article]({item['link']})")

    # RIGHT COLUMN: FILINGS
    with col_filings:
        st.subheader("📄 SEC Filings (Annual & Periodic)")
        if cik_id:
            sec_url = f"https://data.sec.gov/submissions/CIK{cik_id}.json"
            data = requests.get(sec_url, headers=SEC_HEADERS).json()
            recent = data['filings']['recent']
            
            for i in range(10): # Show last 10 for more options
                form, date, doc = recent['form'][i], recent['filingDate'][i], recent['primaryDocument'][i]
                acc = recent['accessionNumber'][i].replace('-', '')
                link = f"https://www.sec.gov/Archives/edgar/data/{cik_id}/{acc}/{doc}"
                
                with st.container(border=True):
                    r1, r2 = st.columns([4, 1.5])
                    r1.markdown(f"**{date}** | `{form}`")
                    if r2.button("Analyze Impact", key=f"f_{i}"):
                        if not client:
                            st.error("Please enter your OpenAI API Key in the sidebar.")
                        else:
                            with st.spinner("Analyzing business narrative..."):
                                content = get_filing_text(link)
                                prompt = f"As a hedge fund analyst, summarize the business impact of this {form} filing for {ticker} in 3 bullet points. Focus on strategy and future outlook."
                                res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": f"{prompt}\n\nContent: {content}"}])
                                st.info(res.choices[0].message.content)
        else:
            st.error("Ticker not found.")
