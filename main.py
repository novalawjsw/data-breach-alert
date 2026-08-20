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
            if int(float(num_str.replace(',', '')) * 100_000_000) >= 1: return True
        except ValueError:
            continue
            
    match_man = re.findall(r'([\d,.]+)\s*만', clean_text)
    for num_str in match_man:
        try:
            if int(float(num_str.replace(',', '')) * 10_000) >= 1: return True
        except ValueError:
            continue
            
    match_raw = re.findall(r'([\d,]+)\s*(?:명|건|개|계정)', clean_text)
    for num_str in match_raw:
        try:
            if int(num_str.replace(',', '')) >= 1: return True
        except ValueError:
            continue
            
    return False

def send_telegram_alert(title, link):
    message = f"🚨 [개인정보 유출 알림]\n\n📌 테스트 중 (1명 이상)\n📰 제목: {title}\n🔗 링크: {link}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
    
    # 텔레그램 서버의 실제 응답 결과를 깃허브 로그에 출력합니다.
    print(f"텔레그램 발송 시도 - 상태 코드: {response.status_code}, 응답 결과: {response.text}")

def check_news():
    # 깃허브 Secrets에서 키를 제대로 불러왔는지 확인합니다.
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("오류: 텔레그램 API 키가 없습니다. GitHub Secrets 설정을 확인해주세요.")
        return
        
    print(f"💡 불러온 토큰 확인(앞 5자리): {TELEGRAM_BOT_TOKEN[:5]}... / 챗 ID: {TELEGRAM_CHAT_ID}")
    
    print("--- 🤖 테스트 메시지 발송 시작 ---")
    send_telegram_alert("🤖 텔레그램 연결 테스트입니다!", "https://google.com")
    print("--- 🤖 테스트 메시지 발송 완료 ---")

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
