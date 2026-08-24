import os
import re
import requests
import urllib.parse
import xml.etree.ElementTree as ET
import datetime
from email.utils import parsedate_to_datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 중복 방지를 위한 텍스트 파일 (깃허브 저장소에 직접 남김)
DB_PATH = "seen_articles.txt"

def load_db():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        return []

def save_db(db_list):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        for item in db_list:
            f.write(f"{item}\n")

def parse_victim_count(text):
    clean_text = text.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&apos;", "'")
    
    match_eok = re.findall(r'([\d,.]+)\s*억\s*(?:천\s*)?(?:만\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_eok:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 100_000_000) >= 5_000_000: return True
        except ValueError: continue

    match_man_unit = re.findall(r'([\d,.]+)\s*만\s*(?:천\s*)?(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_man_unit:
        try:
            num = float(num_str.replace(',', ''))
            if int(num * 10_000) >= 5_000_000: return True
        except ValueError: continue

    matches_man_general = re.finditer(r'([\d,.]+)\s*만', clean_text)
    for m in matches_man_general:
        after_text = clean_text[m.end():m.end()+15]
        if re.search(r'^\s*(?:원|달러|엔|유로|과징금|손실|매출|이익|벌금|배상|부과)', after_text):
            continue
        try:
            num = float(m.group(1).replace(',', ''))
            if int(num * 10_000) >= 5_000_000: return True
        except ValueError: continue

    match_raw = re.findall(r'([\d,]+)\s*(?:명|건|개|계정|회원|인)', clean_text)
    for num_str in match_raw:
        try:
            num_val = int(num_str.replace(',', ''))
            if num_val >= 5_000_000: return True
        except ValueError: continue

    return False

def is_relevant_nova_news(title):
    keywords = ["유출", "집단소송", "단체소송", "소송", "배상", "보상", "손해배상", "해킹", "피해", "위자료", "고소", "고발", "대응"]
    for keyword in keywords:
        if keyword in title: return True
    return False

def send_telegram_alert(alert_type, title, link):
    if alert_type == "breach":
        message = f"🚨 [대규모 정보 유출 감지]\n\n📌 피해 규모: 500만 건/명 이상\n📰 제목: {title}\n🔗 링크: {link}"
    elif alert_type == "nova":
        message = f"🏢 [Law Firm Nova 모니터링]\n\n📌 관련 업무 보도 감지\n📰 제목: {title}\n🔗 링크: {link}"
    else: return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def process_rss(query, alert_type, seen_links):
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    response = requests.get(url)
    if response.status_code != 200: return seen_links
        
    root = ET.fromstring(response.text)
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for item in root.findall('.//channel/item'):
        title = item.find('title').text
        link = item.find('link').text
        pub_date_str = item.find('pubDate').text
        
        # 주소가 이미 기록장에 있으면 통과 (중복 차단)
        if link in seen_links: continue
            
        if pub_date_str:
            pub_date = parsedate_to_datetime(pub_date_str)
            if (now - pub_date).total_seconds() > 24 * 3600:
                continue 
        
        if alert_type == "breach":
            if parse_victim_count(title):
                send_telegram_alert("breach", title, link)
                seen_links.append(link) # 발송 성공한 기사만 기록장에 추가
        elif alert_type == "nova":
            if is_relevant_nova_news(title):
                send_telegram_alert("nova", title, link)
                seen_links.append(link) # 발송 성공한 기사만 기록장에 추가
                
    return seen_links

def check_news():
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        return

    seen_links = load_db()
    
    query_breach = urllib.parse.quote('"개인정보 유출" OR "고객정보 유출" OR "회원정보 유출" OR "데이터 유출" OR "정보 유출"')
    seen_links = process_rss(query_breach, "breach", seen_links)
    
    query_nova = urllib.parse.quote('"법무법인 노바" OR "이돈호 변호사" OR "이돈호 대표변호사" OR "이돈호 대표"')
    seen_links = process_rss(query_nova, "nova", seen_links)
    
    # 발송된 기사 링크가 추가된 리스트(최대 1000개 유지)를 파일에 저장
    save_db(seen_links[-1000:])

if __name__ == "__main__":
    check_news()
