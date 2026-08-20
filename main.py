import os
import re
import json
import requests
import urllib.parse
import xml.etree.ElementTree as ET

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DB_PATH = "seen_articles.json"

def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_db(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def parse_victim_count(text):
    clean_text = text.replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
    
    match_eok = re.findall(r'([\d,.]+)\s*억', clean_text)
    for num_str in match_eok:
        try:
            if int(float(num_str.replace(',', '')) * 100_000_000) >= 5_000_000: return True
        except ValueError:
            continue
            
    match_man = re.findall(r'([\d,.]+)\s*만', clean_text)
    for num_str in match_man:
        try:
            if int(float(num_str.replace(',', '')) * 10_000) >= 5_000_000: return True
        except ValueError:
            continue
            
    match_raw = re.findall(r'([\d,]+)\s*(?:명|건|개|계정)', clean_text)
    for num_str in match_raw:
        try:
            if int(num_str.replace(',', '')) >= 5_000_000: return True
        except ValueError:
            continue
            
    return False

def send_telegram_alert(title, link):
    message = f"🚨 [대규모 개인정보 유출 알림]\n\n📌 피해 규모: 500만명 이상 추정\n📰 제목: {title}\n🔗 링크: {link}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def check_news():
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Telegram API Key is missing.")
        return

    query = urllib.parse.quote("개인정보 유출")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    response = requests.get(url)
    if response.status_code != 200: return
    
    root = ET.fromstring(response.text)
    seen_links = load_db()
    
    for item in root.findall('.//channel/item'):
        title = item.find('title').text
        link = item.find('link').text
        
        if link in seen_links: continue
        
        if parse_victim_count(title):
            send_telegram_alert(title, link)
        
        seen_links.append(link)
        
    save_db(seen_links[-500:])

if __name__ == "__main__":
    check_news()
