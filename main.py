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
    clean_text = text.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&apos;", "'")
    
    match_eok = re.findall(r'([\d,.]+)\s*억\s*(?:천\s*)?(?:만\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_eok:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 100_000_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    match_man_unit = re.findall(r'([\d,.]+)\s*만\s*(?:천\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_man_unit:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 10_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    matches_man_general = re.finditer(r'([\d,.]+)\s*만', clean_text)
    for m in matches_man_general:
        after_text = clean_text[m.end():m.end()+15]
        if re.search(r'^\s*(?:원|달러|엔|유로|과징금|손실|매출|이익|벌금|배상|부과)', after_text):
            continue
        try:
            num = float(m.group(1).replace(',', ''))
            if int(num * 10_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    match_raw = re.findall(r'([\d,]+)\s*(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_raw:
        try:
            num_val = int(num_str.replace(',', ''))
            if num_val >= 5_000_000:
                return True
        except ValueError:
            continue

    return False

def is_relevant_nova_news(title):
    """자사 뉴스 중 집단소송이나 정보유출 관련 건인지 확인하는 필터"""
    keywords = ["유출", "집단소송", "단체소송", "소송"]
    for keyword in keywords:
        if keyword in title:
            return True
    return False

def send_telegram_alert(alert_type, title, link):
    if alert_type == "breach":
        message = f"🚨 [대규모 개인정보 유출 알림]\n\n📌 피해 규모: 500만 건/명 이상 추정\n📰 제목: {title}\n🔗 링크: {link}"
    elif alert_type == "nova":
        message = f"🏢 [법무법인 노바 뉴스 알림]\n\n📌 집단소송/정보유출 보도 감지\n📰 제목: {title}\n🔗 링크: {link}"
    else:
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def process_rss(query, alert_type, seen_links):
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    response = requests.get(url)
    
    if response.status_code != 200: 
        return seen_links
        
    root = ET.fromstring(response.text)
    for item in root.findall('.//channel/item'):
        title = item.find('title').text
        link = item.find('link').text
        
        if link in seen_links: 
            continue
        
        if alert_type == "breach":
            if parse_victim_count(title):
                send_telegram_alert("breach", title, link)
        elif alert_type == "nova":
            # 이중 필터: 자사 관련 뉴스 중 '유출'이나 '소송' 키워드가 들어간 기사만 발송
            if is_relevant_nova_news(title):
                send_telegram_alert("nova", title, link)
        
        seen_links.append(link)
        
    return seen_links

def check_news():
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Telegram API Key is missing.")
        return

    seen_links = load_db()
    
    # 1. 일반 대규모 개인정보 유출 뉴스 (500만 명 필터)
    query_breach = urllib.parse.quote("개인정보 유출")
    seen_links = process_rss(query_breach, "breach", seen_links)
    
    # 2. 자사 관련 집단소송/유출 뉴스 
    query_nova = urllib.parse.quote('"법무법인 노바" OR "이돈호 변호사"')
    seen_links = process_rss(query_nova, "nova", seen_links)
    
    save_db(seen_links[-1000:])

if __name__ == "__main__":
    check_news()
