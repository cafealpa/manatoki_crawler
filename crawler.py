import concurrent.futures
import mimetypes
import os
import random
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from database import is_url_crawled, add_crawled_url


def create_text_file(download_path, content, file_name="list_url.txt"):
    abs_path = os.path.join(download_path, file_name)
    if not os.path.exists(abs_path):
        with open(abs_path, 'w') as file:
            file.write(content)


def scroll_to_bottom_with_pagedown(driver, stop_event, max_scrolls=500, sleep_time=0.2):
    body = driver.find_element(By.TAG_NAME, "body")
    scroll_count = 0
    while scroll_count < max_scrolls and not stop_event.is_set():
        last_scroll_y = driver.execute_script("return window.scrollY")
        body.send_keys(Keys.PAGE_DOWN)
        scroll_count += 1
        time.sleep(sleep_time)
        new_scroll_y = driver.execute_script("return window.scrollY")
        if new_scroll_y == last_scroll_y:
            break
    time.sleep(2)


def handle_captcha(driver, worker_id, log_callback, stop_event):
    while "bbs/captcha.php" in driver.current_url and not stop_event.is_set():
        log_callback(f"워커 {worker_id}: !! 캡챠 페이지가 감지되었습니다 !! 브라우저에서 직접 해결해주세요.")
        while "bbs/captcha.php" in driver.current_url:
            time.sleep(5)
            if stop_event.is_set(): return
        log_callback(f"워커 {worker_id}: 캡챠가 해결되었습니다.")
        time.sleep(2)


def crawl_worker(worker_id, base_download_path, referer_url, url_list, log_callback, stop_event):
    result = []
    if not url_list:
        return result

    time.sleep(worker_id * 5)

    driver = None
    try:
        driver = Driver(uc=True, headless=False)
        while not stop_event.is_set():
            for url in url_list:
                if len(url_list) == 0:
                    continue

                try:
                    if is_url_crawled(url):
                        log_callback(f"워커 {worker_id}: 이미 크롤링된 URL입니다: {url}")
                        continue

                    log_callback(f"워커 {worker_id}: Navigating to: {url}")
                    driver.get(url)

                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
                    )

                    handle_captcha(driver, worker_id, log_callback, stop_event)
                    if stop_event.is_set(): break

                    scroll_to_bottom_with_pagedown(driver, stop_event)

                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')

                    title_element = soup.find('h1') or soup.find('div', class_='view-title')
                    if title_element:
                        post_title = title_element.get_text(strip=True)
                        if "마나토끼 -" in post_title:
                            post_title = post_title.replace(" > 마나토끼 - 일본만화 허브", "").strip()
                    else:
                        post_title = f"untitled_post_{random.randint(1000, 9999)}"
                    log_callback(f"워커 {worker_id}: Post Title: {post_title}")

                    download_dir = os.path.join(base_download_path, post_title)
                    os.makedirs(download_dir, exist_ok=True)

                    html_mana_section = soup.find('section', itemtype='http://schema.org/NewsArticle')
                    if html_mana_section:
                        img_tags = html_mana_section.find_all('img')
                        log_callback(f"워커 {worker_id}: Found {len(img_tags)} images.")

                        for i, img in enumerate(img_tags):
                            if stop_event.is_set(): break
                            img_url = img.get('src')
                            if img_url and '.gif' not in img_url.lower():
                                try:
                                    header = {'referer': referer_url}
                                    response = requests.get(img_url, stream=True, headers=header, timeout=30)
                                    response.raise_for_status()

                                    content_type = response.headers.get('Content-Type')
                                    ext = mimetypes.guess_extension(content_type) or os.path.splitext(img_url)[1] or ".jpg"
                                    img_filename = os.path.join(download_dir, f"{i + 1:03d}{ext}")
                                    with open(img_filename, 'wb') as f:
                                        f.write(response.content)
                                except requests.exceptions.RequestException as req_err:
                                    log_callback(f"워커 {worker_id}: Error downloading {img_url}: {req_err}")

                        if not stop_event.is_set():
                            add_crawled_url(url, post_title)
                            log_callback(f"워커 {worker_id}: [SUCCESS] 크롤링 완료 - {post_title}")
                            result.append({"state": "SUCCESS", "message": "성공", "title": post_title, "url": url})
                    else:
                        log_callback(f"워커 {worker_id}: [FAIL] mana_section이 없습니다. {url}")
                        result.append({"state": "STOPED", "message": "mana_section이 없습니다.", "title": post_title, "url": url})

                except Exception as e:
                    log_callback(f"워커 {worker_id}: [FAIL] 처리 중 오류 발생 {url}. {e}")
                    result.append({"state": "FAIL", "message": f"[FAIL] 처리 중 오류 발생. {e}", "title": "", "url": url})
            return result
    finally:
        if driver:
            driver.quit()
        log_callback(f"워커 {worker_id}: 종료")


def get_target_pages(driver, target_url, log_callback):
    try:
        log_callback(f"크롤링 대상 목록을 조회합니다: {target_url}")
        driver.get(target_url)
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
            log_callback(f"총 {len(article_urls)}개의 에피소드를 찾았습니다.")
            return article_urls
        else:
            log_callback("만화 목록을 찾을 수 없습니다.")
            return []
    except Exception as e:
        log_callback(f"목록 페이지 로딩 중 에러가 발생했습니다: {e}")
        return []


def master_crawl_thread(params, gui_queue, stop_event):
    def log_callback(message):
        gui_queue.put(('log', message))

    def update_progress_callback(progress):
        gui_queue.put(('progress', progress))

    def on_complete_callback(success):
        gui_queue.put(('complete', success))

    def show_info_callback(message):
        gui_queue.put(('show_info', message))

    target_url = params['target_url']
    download_path = params['download_path']

    parsed_uri = urlparse(target_url)
    referer_url = f'{parsed_uri.scheme}://{parsed_uri.netloc}/'

    num_threads = 3
    if 'num_threads' in params and isinstance(params['num_threads'], str) and params['num_threads'].isdigit():
        num_threads = int(params['num_threads'])
    else:
        # 위의 조건에 맞지 않으면 기본값을 사용합니다.
        print("Warning: 'num_threads' value is not a positive integer string. Using default value.")

    log_callback("크롤링을 시작합니다...")

    list_driver = None
    try:
        list_driver = Driver(uc=True, headless=False)
        article_urls = get_target_pages(list_driver, target_url, log_callback)
    finally:
        if list_driver:
            list_driver.quit()

    if not article_urls:
        log_callback("크롤링할 에피소드가 없습니다.")
        on_complete_callback(False)
        return

    create_text_file(download_path, target_url)

    total_articles = len(article_urls)
    crawled_urls = 0
    target_article_urls = []

    for url in article_urls:
        if is_url_crawled(url):
            crawled_urls += 1
        else:
            target_article_urls.append(url)

    target_article_num = len(target_article_urls)

    log_callback(f"총 {total_articles}개중 이미 수집완료된 {crawled_urls}개는 제외합니다.")

    if target_article_num <= 0:
        log_callback("크롤링할 에피소드가 없습니다.")
        on_complete_callback(False)
        return

    log_callback(f"{len(target_article_urls)}개의 작업을 {num_threads}개의 스레드로 시작합니다.")

    completed_tasks = 0
    success_count = 0
    failed_count = 0

    worker_urls = {i + 1: [] for i in range(num_threads)}
    for i, url in enumerate(target_article_urls):
        worker_id = (i % num_threads) + 1
        worker_urls[worker_id].append(url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_url = {
            executor.submit(crawl_worker, worker_id, download_path, referer_url, url_list_for_worker, log_callback, stop_event): url_list_for_worker
            for worker_id, url_list_for_worker in worker_urls.items()
        }

        for future in concurrent.futures.as_completed(future_to_url):
            if stop_event.is_set():
                break

            try:
                results = future.result()
                completed_tasks += len(results)
                for result in results:
                    if result["state"] == "SUCCESS":
                        success_count += 1
                    else:
                        failed_count += 1
                
                log_callback(f"성공: {success_count}, 실패: {failed_count}")

            except Exception as exc:
                failed_count += 1
                log_callback(f"[치명적 오류] {future_to_url[future]}: {exc}")

            if target_article_num > 0:
                progress = (completed_tasks / target_article_num) * 100
                update_progress_callback(progress)

    if not stop_event.is_set():
        update_progress_callback(100)
        log_callback("\n\n🎉🎉🎉 모든 크롤링 작업이 완료되었습니다.")
        show_info_callback("크롤링이 완료되었습니다.")
    else:
        log_callback("크롤링 작업이 중지되었습니다.")
        show_info_callback("크롤링이 중지되었습니다.")

    on_complete_callback(True)
