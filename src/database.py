
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

def create_tables():
    """'crawled_urls'와 'app_config' 테이블을 생성합니다."""
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()

def get_app_config(key):
    """app_config 테이블에서 값을 가져옵니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_config WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else None

def set_app_config(key, value):
    """app_config 테이블에 값을 저장합니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

def is_url_crawled(url):
    """주어진 URL이 이미 수집되었는지 확인합니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM crawled_urls WHERE url = ?", (url,))
        return cursor.fetchone() is not None

def add_crawled_url(url, page_title):
    """수집 완료된 URL을 데이터베이스에 추가합니다."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO crawled_urls (url, page_title) VALUES (?, ?)", (url, page_title))
            conn.commit()
            print(f"데이터베이스에 추가: {url}")
        except sqlite3.IntegrityError:
            # UNIQUE 제약 조건으로 인해 이미 존재하는 URL은 무시됩니다.
            print(f"이미 데이터베이스에 존재: {url}")


def delete_crawled_urls_by_ids(ids):
    """주어진 ID 목록에 해당하는 수집된 URL들을 삭제합니다."""
    if not ids:
        return 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in ids)
        query = f"DELETE FROM crawled_urls WHERE id IN ({placeholders})"
        cursor.execute(query, ids)
        conn.commit()
        print(f"{cursor.rowcount}개의 항목이 데이터베이스에서 삭제되었습니다.")
        return cursor.rowcount

# 애플리케이션 시작 시 테이블이 없는 경우 생성
create_tables()
