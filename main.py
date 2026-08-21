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
    
    # 1. 억 단위: 피해 단위가 명시된 경우만 인식 (금액 배제)
    match_eok = re.findall(r'([\d,.]+)\s*억\s*(?:천\s*)?(?:만\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_eok:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 100_000_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    # 2. 만 단위: 피해 단위가 명시된 경우
    match_man_unit = re.findall(r'([\d,.]+)\s*만\s*(?:천\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_man_unit:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 10_000) >= 5_000_000:
                return True
        except ValueError:
            continue

    # 3. 단위 생략형 ('500만' 등) 처리 및 화폐/과징금 배제
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

    # 4. 순수 숫자 표기
    match_raw = re.findall(r'([\d,]+)\s*(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_raw:
        try:
            num_val = int(num_str.replace(',', ''))
            if num_val >= 5_000_000:
                return True
        except ValueError:
            continue

    return False

def send_telegram_alert(alert_type, title, link):
    if alert_type == "breach":
        message = f"🚨 [대규모 개인정보 유출 알림]\n\n📌 피해 규모: 500만 건/명 이상 추정\n📰 제목: {title}\n🔗 링크: {link}"
    elif alert_type == "nova":
        message = f"🏢 [법무법인 노바 뉴스 알림]\n\n📌 관련 키워드 보도 감지\n📰 제목: {title}\n🔗 링크: {link}"
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
        
        # 이미 알림을 보낸 기사는 패스
        if link in seen_links: 
            continue
        
        if alert_type == "breach":
            if parse_victim_count(title):
                send_telegram_alert("breach", title, link)
        elif alert_type == "nova":
            # 법무법인 노바 및 이돈호 변호사 관련 뉴스는 유출 규모 판단 없이 무조건 발송
            send_telegram_alert("nova", title, link)
        
        seen_links.append(link)
        
    return seen_links

def check_news():
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Telegram API Key is missing.")
        return

    seen_links = load_db()
    
    # 1. 개인정보 유출 뉴스 모니터링 (500만 명 필터 적용)
    query_breach = urllib.parse.quote("개인정보 유출")
    seen_links = process_rss(query_breach, "breach", seen_links)
    
    # 2. 자사 관련 뉴스 모니터링 (정확도를 위해 큰따옴표 묶음 검색 적용)
    query_nova = urllib.parse.quote('"법무법인 노바" OR "이돈호 변호사"')
    seen_links = process_rss(query_nova, "nova", seen_links)
    
    # 검색량이 2배로 늘었으므로, 중복 방지를 위해 기억하는 기사 수를 1000개로 상향
    save_db(seen_links[-1000:])

if __name__ == "__main__":
    check_news()
