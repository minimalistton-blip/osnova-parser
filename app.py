#!/usr/bin/env python3
"""
Парсер законодательства - стабильная версия для HF Space
"""

import feedparser
import json
import os
import re
import requests
from datetime import datetime, timedelta
from collections import Counter

# ========== КОНФИГУРАЦИЯ ==========
OUTPUT_FILE = "/data/recent_documents.json"  # для HF Space
# OUTPUT_FILE = "recent_documents.json"  # для локального теста

DAYS_TO_KEEP = 30
MAX_POSTS = 300

RSS_FEEDS = {
    "pravo_official": "http://publication.pravo.gov.ru/api/rss?pageSize=200",
    "nalog": "https://www.nalog.gov.ru/rn77/rss/news/",
}

IMPORTANT_WORDS = {
    "ндс": "НДС", "усн": "УСН", "ндфл": "НДФЛ", "налог на прибыль": "Налог на прибыль",
    "страховые взносы": "Страховые взносы", "есхн": "ЕСХН", "патент": "Патент",
    "эдо": "ЭДО", "бюджет": "Бюджет", "персональные данные": "Персональные данные"
}

# ========== ФУНКЦИИ ==========

def generate_stable_id(source: str, link: str) -> str:
    """Генерация стабильного ID документа"""
    match = re.search(r'(?:eoNumber|document|id[=_])=?(\d+)', link, re.IGNORECASE)
    if match:
        return f"{source}_{match.group(1)}"
    
    match = re.search(r'/(\d{4,})(?:/|\.html?)?$', link)
    if match:
        return f"{source}_{match.group(1)}"
    
    return f"{source}_{abs(hash(link)) % 100000000}"


def extract_document_type_and_number(title: str) -> tuple:
    """Извлекает тип документа и номер"""
    patterns = {
        "Указ Президента РФ": r"Указ Президента.*?№?\s*(\d+)",
        "Постановление Правительства РФ": r"Постановление Правительства.*?№?\s*(\d+)",
        "Федеральный закон": r"Федеральный закон.*?№?\s*(\d+-ФЗ)",
        "Приказ": r"Приказ.*?№?\s*([А-Я0-9-]+)",
        "Распоряжение": r"Распоряжение.*?№?\s*(\d+)",
        "Письмо": r"Письмо.*?№?\s*([А-Я0-9-]+)",
    }
    
    for doc_type, pattern in patterns.items():
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return doc_type, match.group(1).strip()
    return None, None


def extract_tags(title: str):
    title_lower = title.lower()
    return [tag for keyword, tag in IMPORTANT_WORDS.items() if keyword in title_lower]


def parse_date(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except:
        try:
            return datetime.strptime(date_str[:10], "%d.%m.%Y")
        except:
            return None


def fetch_with_headers(url: str):
    """Скачивает содержимое с правильными заголовками"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, timeout=25, headers=headers)
    response.raise_for_status()
    return response.content


def parse_feed(source: str, url: str, cutoff_date: datetime):
    posts = []
    try:
        if "pravo.gov.ru" in url:
            content = fetch_with_headers(url)
            feed = feedparser.parse(content)
        else:
            feed = feedparser.parse(url)

        for entry in feed.entries[:100]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            pub_date = parse_date(entry.get("published") or entry.get("pubDate") or "")
            if pub_date and pub_date < cutoff_date:
                continue

            pub_date_display = pub_date.strftime("%d.%m.%Y") if pub_date else datetime.now().strftime("%d.%m.%Y")

            doc_type, doc_number = extract_document_type_and_number(title)

            if not doc_type:
                doc_type = {
                    "pravo_official": "Нормативный акт",
                    "nalog": "Новость ФНС",
                }.get(source, "Документ")

            posts.append({
                "id": generate_stable_id(source, link),
                "source": source,
                "source_url": link,
                "title": title[:600],
                "publish_date": pub_date_display,
                "document_type": doc_type,
                "document_number": doc_number,
                "full_text_url": link,
                "effective_date": None,
                "tags": extract_tags(title),
                "processed": False,
                "added_at": datetime.now().isoformat(),
            })

        print(f"   ✅ Найдено: {len(posts)}")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    return posts


def main():
    print("\n" + "=" * 75)
    print("🚀 ЗАПУСК ПАРСЕРА ОСНОВА (Stable Light)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75 + "\n")

    cutoff_date = datetime.now() - timedelta(days=DAYS_TO_KEEP)
    all_posts = []

    for source, url in RSS_FEEDS.items():
        print(f"📡 Парсинг: {source}")
        posts = parse_feed(source, url, cutoff_date)
        all_posts.extend(posts)

    all_posts.sort(key=lambda x: x["publish_date"], reverse=True)
    if len(all_posts) > MAX_POSTS:
        all_posts = all_posts[:MAX_POSTS]

    # Создаём директорию, если её нет
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_posts": len(all_posts),
            "posts": all_posts
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Сохранено {len(all_posts)} документов → {OUTPUT_FILE}")
    
    # Статистика по источникам
    sources = Counter(p["source"] for p in all_posts)
    print("\n📊 Источники:")
    for s, c in sources.most_common():
        print(f"   {s}: {c}")

    print("=" * 75)

if __name__ == "__main__":
    main()