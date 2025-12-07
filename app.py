"""
Self-Healing DOM Scraper (Local Production Version)
===================================================
A Streamlit UI that acts as the "Control Center" for your Autonomous Agent.

Features:
- Connects to local Ollama (dom-specialist model)
- Hybrid Extraction: JSON-LD -> CSS Selectors -> Text Fallback
- Anti-Bot: Auto-switches to Selenium/Undetected-Chromedriver if needed

Note: 
The training notebook and local script runs in 'Research Mode' (bypassing restrictions) to 
generate synthetic training data and test out the fine-tuned model.
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
from datetime import datetime

# DEPENDENCY CHECK: Graceful Degradation for Anti-Bot
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium_stealth import stealth
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# CONFIGURATION
st.set_page_config(page_title="Self-Healing Scraper", page_icon="🚑", layout="wide")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "dom-specialist"  # The model you created with 'ollama create'
ANTI_BOT_SITES = ['stockx.com', 'nike.com', 'adidas.com', 'footlocker.com', 'shopify.com']

# CORE LOGIC CLASSES
class ScraperLogic:
    @staticmethod
    def extract_subject(intent):
        """
        NLP Logic: Extracts the 'Subject' from the query to focus the AI's vision.
        Input: "Extract the movie director name" -> Output: "director"
        """
        stop_words = {"extract", "find", "get", "the", "a", "an", "of", "value", "text", "name", "movie", "page", "webpage", "site"}
        words = re.findall(r'\w+', intent.lower())
        candidates = [w for w in words if w not in stop_words]
        return candidates[-1] if candidates else (words[-1] if words else "data")

    @staticmethod
    def smart_clean_html(html_content, target_keyword=None):
        """
        Context Engineering: Reduces HTML noise to prevent token overflow.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. Remove non-content tags
        for element in soup(["script", "style", "footer", "nav", "header", "svg", "button", "meta", "noscript", "iframe", "ad"]):
            # Preserve JSON-LD scripts, remove others
            if element.name == 'script' and element.get('type') == 'application/ld+json':
                continue
            element.decompose()
        
        # 2. Extract Text Structure (for Fallback)
        text_structure = soup.get_text(separator="\n", strip=True)
        
        # 3. Create Focused HTML Window
        body_text = str(soup.body) if soup.body else str(soup)
        
        if target_keyword:
            # Find the keyword in the raw HTML
            idx = body_text.lower().find(target_keyword.lower())
            if idx != -1:
                # Create a window: 500 chars before, 1500 chars after (Tighter window to avoid distraction)
                start = max(0, idx - 500)
                end = min(len(body_text), idx + 1500)
                return f"...{body_text[start:end]}...", text_structure
        
        return body_text[:4000], text_structure

    @staticmethod
    def parse_json_ld(soup):
        """Extracts structured data (Product, Price) from JSON-LD tags."""
        data_found = {}
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list): data = data[0] if data else {}
                
                # Standard E-Commerce Fields
                if 'name' in data: data_found['name'] = data['name']
                if 'description' in data: data_found['description'] = data['description']
                if 'offers' in data:
                    offer = data['offers'] if isinstance(data['offers'], dict) else data['offers'][0]
                    data_found['price'] = f"{offer.get('priceCurrency', '')} {offer.get('price', '')}"
            except:
                continue
        return data_found

# AI INTERFACE (OLLAMA)
def ask_ollama(prompt, temperature=0.1):
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192,
                "stop": ["<|im_end|>", "\n"]
            }
        }, timeout=30)
        
        if response.status_code == 200:
            return response.json()['response'].strip()
        return None
    except Exception as e:
        st.error(f"Ollama Connection Error: {e}")
        return None

def generate_selector(html_snippet, intent):
    prompt = f"""<|im_start|>system
You are a DOM-aware agent. Return ONLY the CSS selector for the user's intent. Do not explain.<|im_end|>
<|im_start|>user
Intent: {intent}
HTML:
{html_snippet}<|im_end|>
<|im_start|>assistant
"""
    return ask_ollama(prompt, temperature=0.1)

def direct_extraction(text_context, intent):
    prompt = f"""<|im_start|>system
Extract the exact answer. 
- Return ONLY the entity requested.
- If asked for Director, do NOT return Actors.
- If asked for Price, do NOT return Tax.<|im_end|>
<|im_start|>user
Request: {intent}
Context:
{text_context}<|im_end|>
<|im_start|>assistant
"""
    return ask_ollama(prompt, temperature=0.05)

# BROWSER ENGINE
def fetch_html(url):
    """Hybrid Fetcher: Uses Requests for speed, Selenium for Anti-Bot."""
    
    # 1. Check for Anti-Bot Sites
    is_hard_target = any(x in url for x in ANTI_BOT_SITES)
    
    if is_hard_target and SELENIUM_AVAILABLE:
        st.toast("🛡️ Anti-Bot Detected: Switching to Stealth Mode...", icon="🤖")
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        driver = uc.Chrome(options=options)
        try:
            driver.get(url)
            time.sleep(5) # Wait for hydration
            return driver.page_source
        finally:
            driver.quit()
            
    # 2. Standard Requests
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        resp = requests.get(url, headers=headers, timeout=10)
        return resp.text
    except Exception as e:
        return None

# MAIN UI LOOP
st.title("🚑 Self-Healing Scraper V4")
st.caption("Local Agent | Ollama | Selenium | JSON-LD")

col1, col2 = st.columns([1, 1])

with col1:
    url = st.text_input("Target URL", "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html")
    intent = st.text_input("Intent", "Extract the price")
    simulate_break = st.checkbox("Simulate Broken Selector (Force Heal)", value=True)

    if st.button("🚀 Launch Agent", type="primary"):
        if not url or not intent:
            st.error("Please enter a URL and Intent.")
            st.stop()

        status = st.status("Initializing Agent...", expanded=True)
        
        # 1. Fetch
        status.write(f"🌐 Connecting to {url}...")
        html = fetch_html(url)
        if not html:
            status.update(label="❌ Failed to load page.", state="error")
            st.stop()
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 2. Try Cache (Simulation)
        cached_selector = ".old-broken-selector" if simulate_break else None
        if cached_selector:
            status.write(f"⚡ Trying Cached Selector: `{cached_selector}`")
            time.sleep(0.5)
            # It will fail
            status.write("❌ Cache Failed! Element not found.")
            
        # 3. Try JSON-LD (Fastest Path)
        status.write("🔍 Checking JSON-LD Structured Data...")
        json_data = ScraperLogic.parse_json_ld(soup)
        subject = ScraperLogic.extract_subject(intent)
        
        if 'price' in subject and 'price' in json_data:
            status.update(label=f"✅ Found in Metadata: {json_data['price']}", state="complete")
            st.success(f"Extracted: {json_data['price']}")
            st.stop()
            
        # 4. Trigger AI Healing
        status.write("🚑 Engaging AI Healing Protocol...")
        
        # Context Engineering
        status.write(f"🧠 Focusing vision on subject: '{subject}'")
        focused_html, text_structure = ScraperLogic.smart_clean_html(html, subject)
        
        # Strategy A: Generate Selector
        status.write("💡 Generating new CSS Selector...")
        new_selector = generate_selector(focused_html, intent)
        status.write(f"👉 AI Suggested: `{new_selector}`")
        
        try:
            element = soup.select_one(new_selector)
            if element and len(element.get_text(strip=True)) > 0:
                result = element.get_text(strip=True)
                status.update(label=f"✅ HEALED (Selector)! Result: {result}", state="complete")
                st.success(result)
                st.balloons()
                st.stop()
        except:
            status.write("⚠️ Selector failed. Switching to Text Extraction...")
            
        # Strategy B: Direct Text Extraction (Fallback)
        status.write("🛡️ Fallback: Reading Page Text...")
        direct_result = direct_extraction(text_structure[:4000], intent)
        
        if direct_result:
            status.update(label=f"✅ HEALED (Text)! Result: {direct_result}", state="complete")
            st.success(direct_result)
            st.balloons()
        else:
            status.update(label="❌ All strategies failed.", state="error")

with col2:
    st.info("ℹ️ **System Status**")
    try:
        req = requests.get("http://localhost:11434/api/tags")
        if req.status_code == 200:
            st.success("🟢 Ollama Online")
        else:
            st.error("🔴 Ollama Offline")
    except:
        st.error("🔴 Ollama Connection Failed")
        
    st.write("---")
    st.write("**Debug View:**")
    st.code("", language="html")