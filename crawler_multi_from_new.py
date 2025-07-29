

import concurrent.futures
import mimetypes
import os
import random
import queue
import time
import sys

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from database import is_url_crawled, add_crawled_url

# 스레드 4개부터 IP block 됨.
NUM_THREADS = 3

def scroll_to_bottom_with_pagedown(driver, max_scrolls=80, sleep_time=0.2):
    print("페이지의 끝까지 스크롤을 시작합니다...")
    body = driver.find_element(By.TAG_NAME, "body")
    scroll_count = 0
    last_scroll_y = driver.execute_script("return window.scrollY")

    while scroll_count < max_scrolls:
        # print(f"현재 스크롤 위치: {last_scroll_y}")
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(sleep_time)

        current_scroll_y = driver.execute_script("return window.scrollY")
        # print(f"스크롤 후 위치: {current_scroll_y}")

        if current_scroll_y == last_scroll_y:
            print("페이지의 마지막에 도달하여 스크롤을 중단합니다.")
            break

        last_scroll_y = current_scroll_y
        scroll_count += 1
    else:
        print(f"최대 스크롤 횟수({max_scrolls})에 도달했습니다.")
    
    time.sleep(1)


def handle_captcha(driver):
    while "bbs/captcha.php" in driver.current_url:
        print("\n" + "=" * 50)
        print("!! 캡챠 페이지가 감지되었습니다 !!")
        print("브라우저에서 직접 캡챠를 풀어주세요.")
        input("완료하고 터미널에서 Enter를 누르세요.......")
        print("=" * 50 + "\n")
        time.sleep(2)


def crawl_worker(q, worker_id):
    # 워커 id(1,2,3) * 5 만큼 기다림. driver 초기화 문제 해결
    time.sleep(worker_id * 5)

    driver = None
    try:

        driver = Driver(uc=True, headless=False)

        while True:
            url = q.get()

            # 큐에서 독약을 받으면 루프를 종료하고 스레드를 마침
            if url is None:
                q.task_done()
                break

            try:
                if is_url_crawled(url):
                    print(f"워커 {worker_id}: 이미 크롤링된 URL입니다: {url}")
                    continue

                print(f"워커 {worker_id}: Navigating to: {url}")
                driver.get(url)

                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
                )

                handle_captcha(driver)
                scroll_to_bottom_with_pagedown(driver)

                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

                title_element = soup.find('h1')
                if not title_element:
                    title_element = soup.find('div', class_='view-title')

                if title_element:
                    post_title = title_element.get_text(strip=True)
                    if "마나토끼 -" in post_title:
                        post_title = post_title.replace(" > 마나토끼 - 일본만화 허브", "").strip()
                    print(f"워커 {worker_id}: Post Title: {post_title}")
                else:
                    post_title = f"untitled_post_{random.randint(1000, 9999)}"
                    print(f"워커 {worker_id}: Could not find post title. Using default name: {post_title}")

                download_dir = os.path.join("download_mana", post_title)
                os.makedirs(download_dir, exist_ok=True)

                html_mana_section = soup.find('section', itemtype='http://schema.org/NewsArticle')
                if html_mana_section:
                    img_tags = html_mana_section.find_all('img')
                    print(f"워커 {worker_id}: Found {len(img_tags)} images.")

                    for i, img in enumerate(img_tags):
                        img_url = img.get('src')
                        if img_url and '.gif' not in img_url.lower():
                            try:
                                header = {'referer': 'https://manatoki468.net/'}
                                response = requests.get(img_url, stream=True, headers=header, timeout=30)
                                response.raise_for_status()

                                content_type = response.headers.get('Content-Type')
                                ext = mimetypes.guess_extension(content_type) if content_type else os.path.splitext(img_url)[1]
                                if not ext: ext = ".jpg"

                                img_filename = os.path.join(download_dir, f"{i + 1:03d}{ext}")
                                with open(img_filename, 'wb') as f:
                                    for chunk in response.iter_content(1024):
                                        f.write(chunk)
                                print(f"워커 {worker_id}: Downloaded {img_filename}")
                            except requests.exceptions.RequestException as req_err:
                                print(f"워커 {worker_id}: Error downloading {img_url}: {req_err}")

                    add_crawled_url(url, post_title)
                    print(f"워커 {worker_id}: [SUCCESS] 크롤링 완료 - {post_title}")
                else:
                    print(f"워커 {worker_id}: [FAIL] 크롤링 실패 - mana_section 이 없다. {url}")
            except Exception as e:
                print(f"워커 {worker_id}: [FAIL] 처리중 오류 발생 {url}. {e}")
            finally:
                q.task_done()
                time.sleep(random.randint(1, 3))

    finally:
        if driver:
            driver.quit()
        print(f"워커 {worker_id}: 종료")


def get_target_pages(driver: Driver, target_url) -> list:
    print(f"크롤링 대상 목록을 조회 합니다.")
    try:
        driver.get(target_url)
        print(f"Successfully opened {target_url}")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
        )
        
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        article_body = soup.find('article', itemprop='articleBody')
        if article_body:
            serial_list_div = article_body.find('div', class_='serial-list')
            links = serial_list_div.find_all('a', href=True) if serial_list_div else []
            article_urls = [link['href'] for link in links]
            print("Found articleBody. Extracted URLs:")
            for url in article_urls:
                print(url)
            return article_urls
        else:
            print("만화 목록이 없네요.")
            return []
    except Exception as e:
        print(f"에러가 발생했습니다: {e}")
    return []


def main():
    os.makedirs("download_mana", exist_ok=True)

    target_url = ""
    while not target_url:
        target_url = input("크롤링 할 만화 목록 페이지 URL을 입력하세요: ")
        if not target_url:
            print("URL이 입력되지 않았습니다.")
        else:
            confirm = input(f"{target_url} 맞나요?(Y/n) ")
            if confirm.lower() not in ["", "y", "yes", "예"]:
                target_url = ""

    print("크롤링을 시작합니다.")

    article_urls = []
    # print("테스트용 더미 URL 목록을 사용합니다.")
    # article_urls = dummy_url_list

    # 목록조회는 캡챠 없음. headless 모드
    driver = Driver(uc=True, headless=False)
    try:
        article_urls = get_target_pages(driver, target_url)
        if not article_urls:
            print("크롤링할 페이지가 없습니다.")
            return
    finally:
        driver.quit()

    crawl_queue = queue.Queue()
    for url in article_urls:
        crawl_queue.put(url)


    print(f"{crawl_queue.qsize()}개의 작업을 {NUM_THREADS}개의 스래드로 시작합니다.")

    # 독약(Poison Pill) 패턴: 작업 종료를 위해 스레드 수만큼 None을 큐에 추가
    for _ in range(NUM_THREADS):
        crawl_queue.put(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(crawl_worker, crawl_queue, i + 1) for i in range(NUM_THREADS)]
        # concurrent.futures.wait(futures)
        crawl_queue.join()

    print("\n\n🎉🎉🎉 모든 크롤링 작업이 완료되었습니다.")
    # 종료
    sys.exit(0)


if __name__ == "__main__":
    main()
