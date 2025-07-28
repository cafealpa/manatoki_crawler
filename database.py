
import sqlite3
from contextlib import contextmanager

DB_FILE = 'crawled_pages.db'

@contextmanager
def get_db_connection():
    """데이터베이스 연결을 관리하는 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def create_table():
    """'crawled_urls' 테이블을 생성합니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawled_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                page_title TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_url_crawled(url):
    """주어진 URL이 이미 크롤링되었는지 확인합니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM crawled_urls WHERE url = ?", (url,))
        return cursor.fetchone() is not None

def add_crawled_url(url, page_title):
    """크롤링 완료된 URL을 데이터베이스에 추가합니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO crawled_urls (url, page_title) VALUES (?, ?)", (url, page_title))
            conn.commit()
            print(f"데이터베이스에 추가: {url}")
        except sqlite3.IntegrityError:
            # UNIQUE 제약 조건으로 인해 이미 존재하는 URL은 무시됩니다.
            print(f"이미 데이터베이스에 존재: {url}")

# 애플리케이션 시작 시 테이블이 없는 경우 생성
create_table()
