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
    
    # 1. 억 단위: 반드시 피해 단위(명/건/개/계정/회원)가 붙은 경우만 인식 ('540억원', '과징금 540억' 등 금액 제외)
    match_eok = re.findall(r'([\d,.]+)\s*억\s*(?:천\s*)?(?:만\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_eok:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 100_000_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    # 2. 만 단위: 피해 단위(명/건/개/계정/회원)가 명시되어 있고 500만 이상인 경우 (예: 1253만건, 500만명)
    match_man_unit = re.findall(r'([\d,.]+)\s*만\s*(?:천\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_man_unit:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 10_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    # 3. 단위 생략 '500만' 형태이나 뒤에 화폐/과징금 관련 단어가 붙지 않은 경우
    matches_man_general = re.finditer(r'([\d,.]+)\s*만', clean_text)
    for m in matches_man_general:
        after_text = clean_text[m.end():m.end()+15]
        # 뒤에 '원', '과징금', '손실', '매출', '벌금', '배상', '부과' 등이 이어지면 금액이므로 스킵
        if re.search(r'^\s*(?:원|달러|엔|유로|과징금|손실|매출|이익|벌금|배상|부과)', after_text):
            continue
        try:
            num = float(m.group(1).replace(',', ''))
            if int(num * 10_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    # 4. 순수 숫자 표기 (예: 5,000,000명 / 10,000,000건)
    match_raw = re.findall(r'([\d,]+)\s*(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_raw:
        try:
            num_val = int(num_str.replace(',', ''))
            if num_val >= 5_000_000:
                return True
        except ValueError:
            continue

    return False

def send_telegram_alert(title, link):
    message = f"🚨 [대규모 개인정보 유출 알림]\n\n📌 피해 규모: 500만 건/명 이상 추정\n📰 제목: {title}\n🔗 링크: {link}"
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
