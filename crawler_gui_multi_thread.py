import concurrent.futures
import mimetypes
import os
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from database import is_url_crawled, add_crawled_url

# --- Global Variables ---
master_thread = None
stop_event = threading.Event()


# crawl_queue = queue.Queue()

# --- Logging Function ---
def log(message):
    """Inserts a message into the log text area in a thread-safe way."""
    log_text.insert(tk.END, message + "\n")
    log_text.see(tk.END)
    root.update_idletasks()


def browse_directory():
    """Opens a dialog to select a download directory."""
    path = filedialog.askdirectory()
    if path:
        download_path_entry.delete(0, tk.END)
        download_path_entry.insert(0, path)


# --- Crawler Functions ---
def scroll_to_bottom_with_pagedown(driver, max_scrolls=80, sleep_time=0.2):
    # log("페이지의 끝까지 스크롤을 시작합니다...")
    body = driver.find_element(By.TAG_NAME, "body")
    scroll_count = 0
    while scroll_count < max_scrolls and not stop_event.is_set():
        last_scroll_y = driver.execute_script("return window.scrollY")
        body.send_keys(Keys.PAGE_DOWN)
        scroll_count += 1
        time.sleep(sleep_time)
        new_scroll_y = driver.execute_script("return window.scrollY")
        if new_scroll_y == last_scroll_y:
            # log("페이지의 마지막에 도달하여 스크롤을 중단합니다.")
            break
    else:
        log(f"최대 스크롤 횟수({max_scrolls})에 도달했습니다.")
    time.sleep(2)


def handle_captcha(driver, worker_id):
    while "bbs/captcha.php" in driver.current_url and not stop_event.is_set():
        log(f"워커 {worker_id}: !! 캡챠 페이지가 감지되었습니다 !! 브라우저에서 직접 해결해주세요.")
        while "bbs/captcha.php" in driver.current_url:
            time.sleep(5)
            if stop_event.is_set(): return
        log(f"워커 {worker_id}: 캡챠가 해결되었습니다.")
        time.sleep(2)


def crawl_worker(worker_id, base_download_path, url_list):
    """The function each thread will execute to crawl pages."""
    time.sleep(worker_id * 5)  # Stagger driver initialization
    driver = None
    try:

        result = []

        driver = Driver(uc=True, headless=False)
        while not stop_event.is_set():
            for url in url_list:
                # url = crawl_queue.get(timeout=1)
                if len(url_list) == 0:
                    continue  # Check stop_event again

                try:
                    # if is_url_crawled(url):
                    #     log(f"워커 {worker_id}: 이미 크롤링된 URL입니다: {url}")
                    #     continue

                    log(f"워커 {worker_id}: Navigating to: {url}")
                    driver.get(url)

                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
                    )

                    handle_captcha(driver, worker_id)
                    if stop_event.is_set(): break

                    scroll_to_bottom_with_pagedown(driver)

                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')

                    title_element = soup.find('h1') or soup.find('div', class_='view-title')
                    if title_element:
                        post_title = title_element.get_text(strip=True)
                        if "마나토끼 -" in post_title:
                            post_title = post_title.replace(" > 마나토끼 - 일본만화 허브", "").strip()
                    else:
                        post_title = f"untitled_post_{random.randint(1000, 9999)}"
                    log(f"워커 {worker_id}: Post Title: {post_title}")

                    download_dir = os.path.join(base_download_path, post_title)
                    os.makedirs(download_dir, exist_ok=True)

                    html_mana_section = soup.find('section', itemtype='http://schema.org/NewsArticle')
                    if html_mana_section:
                        img_tags = html_mana_section.find_all('img')
                        log(f"워커 {worker_id}: Found {len(img_tags)} images.")

                        for i, img in enumerate(img_tags):
                            if stop_event.is_set(): break
                            img_url = img.get('src')
                            if img_url and '.gif' not in img_url.lower():
                                try:
                                    header = {'referer': 'https://manatoki468.net/'}
                                    response = requests.get(img_url, stream=True, headers=header, timeout=30)
                                    response.raise_for_status()

                                    content_type = response.headers.get('Content-Type')
                                    ext = mimetypes.guess_extension(content_type) or os.path.splitext(img_url)[1] or ".jpg"
                                    img_filename = os.path.join(download_dir, f"{i + 1:03d}{ext}")
                                    with open(img_filename, 'wb') as f:
                                        f.write(response.content)
                                    # log(f"워커 {worker_id}: Downloaded {img_filename}")
                                except requests.exceptions.RequestException as req_err:
                                    log(f"워커 {worker_id}: Error downloading {img_url}: {req_err}")

                        if not stop_event.is_set():
                            add_crawled_url(url, post_title)
                            log(f"워커 {worker_id}: [SUCCESS] 크롤링 완료 - {post_title}")
                            result.append({"state": "SUCCESS", "message": "성공", "title": post_title, "url": url})
                    else:
                        log(f"워커 {worker_id}: [FAIL] mana_section이 없습니다. {url}")
                        result.append({"state": "STOPED", "message": "mana_section이 없습니다.", "title": post_title, "url": url})

                except Exception as e:
                    log(f"워커 {worker_id}: [FAIL] 처리 중 오류 발생 {url}. {e}")
                    result.append({"state": "FAIL", "message": f"[FAIL] 처리 중 오류 발생. {e}", "title": post_title, "url": url})
        # future 반환
        return result
    finally:
        if driver:
            driver.quit()
        log(f"워커 {worker_id}: 종료")


def get_target_pages(driver, target_url):
    try:
        log(f"크롤링 대상 목록을 조회합니다: {target_url}")
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
            log(f"총 {len(article_urls)}개의 에피소드를 찾았습니다.")
            return article_urls
        else:
            log("만화 목록을 찾을 수 없습니다.")
            return []
    except Exception as e:
        log(f"목록 페이지 로딩 중 에러가 발생했습니다: {e}")
        return []


def master_crawl_thread():
    target_url = url_entry.get()
    if not target_url:
        messagebox.showerror("오류", "URL을 입력하세요.")
        return

    download_path = download_path_entry.get()
    if not download_path:
        download_path = "download_mana"
        log(f"다운로드 경로가 지정되지 않아 기본 폴더 '{download_path}'에 저장합니다.")
    os.makedirs(download_path, exist_ok=True)

    crawl_type = url_type.get()
    if crawl_type != "목록":
        messagebox.showinfo("알림", "현재 '목록' 유형만 지원합니다.")
        return

    try:
        num_threads = int(num_threads_entry.get())
        if not 1 <= num_threads <= 10:
            raise ValueError()
    except ValueError:
        messagebox.showerror("오류", "스레드 개수는 1에서 10 사이의 숫자여야 합니다.")
        return

    log("크롤링을 시작합니다...")
    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)
    progress_bar['value'] = 0
    stop_event.clear()

    # Clear queue from previous runs
    # while not crawl_queue.empty():
    #     crawl_queue.get_nowait()

    list_driver = None
    try:
        list_driver = Driver(uc=True, headless=False)
        article_urls = get_target_pages(list_driver, target_url)
    finally:
        if list_driver:
            list_driver.quit()

    if not article_urls:
        log("크롤링할 에피소드가 없습니다.")
        start_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        return

    # 수집된 URL 중 이미 수집된 URL 제외
    total_articles = len(article_urls)
    crawled_urls = 0
    target_article_urls = []

    for url in article_urls:
        if is_url_crawled(url):
            crawled_urls += 1
        else:
            target_article_urls.append(url)

    target_article_num = len(target_article_urls)

    # for url in target_article_urls:
    #     crawl_queue.put(url)

    log(f"총 {total_articles}개중 이미 수집완료된 {crawled_urls}개는 제외합니다.")
    log(f"{len(target_article_urls)}개의 작업을 {num_threads}개의 스레드로 시작합니다.")

    completed_tasks = 0
    success_count = 0
    failed_count = 0

    # target_article_urls을 (i % num_threads) + 1 값으로 분류해서 List로 만듭니다.
    # 각 워커에 할당될 URL 리스트를 저장할 딕셔너리
    worker_urls = {i + 1: [] for i in range(num_threads)}

    # URL을 워커 ID에 따라 분배
    for i, url in enumerate(target_article_urls):
        worker_id = (i % num_threads) + 1
        worker_urls[worker_id].append(url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_url = {
            executor.submit(crawl_worker, worker_id, download_path, url_list_for_worker): url_list_for_worker
            for worker_id, url_list_for_worker in worker_urls.items()
        }

        for future in concurrent.futures.as_completed(future_to_url):
            # Signal workers to stop
            if stop_event.is_set():
                # 중지
                break

            completed_tasks += 1
            try:
                # 워커의 return 값을 가져옵니다.
                result_list = future.result()
                for result in result_list:
                    if result["status"] == "SUCCESS":
                        success_count += 1
                        log(f"[성공] {result["message"]}")
                    elif result["status"] == "FAILED":
                        failed_count += 1
                        log(f"[실패] {result["message"]}")
                    elif result["status"] == "SKIPPED":
                        # 이 경우는 미리 필터링해서 발생하지 않지만, 안정성을 위해 둡니다.
                        log(f"[건너뜀] {result["message"]}")

            except Exception as exc:
                # future.result() 자체에서 예외가 발생한 경우 (매우 드묾)
                failed_count += 1
                log(f"[치명적 오류] {future_to_url[future]}: {exc}")

            # 진행률을 정확하게 업데이트
            progress = (completed_tasks / target_article_num) * 100
            progress_bar['value'] = progress

    if not stop_event.is_set():
        progress_bar['value'] = 100
        log("\n\n🎉🎉🎉 모든 크롤링 작업이 완료되었습니다.")
        messagebox.showinfo("완료", "크롤링이 완료되었습니다.")
    else:
        log("크롤링 작업이 중지되었습니다.")
        messagebox.showinfo("중지", "크롤링이 중지되었습니다.")

    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)
    progress_bar['value'] = 0


def start_crawling():
    global master_thread
    master_thread = threading.Thread(target=master_crawl_thread)
    master_thread.daemon = True
    master_thread.start()


def stop_crawling():
    if master_thread and master_thread.is_alive():
        log("크롤링 중지를 요청했습니다...")
        stop_event.set()


def on_closing():
    if messagebox.askokcancel("종료", "크롤러를 종료하시겠습니까?"):
        stop_event.set()
        if master_thread and master_thread.is_alive():
            master_thread.join()
        root.destroy()


# --- UI Setup ---
root = tk.Tk()
root.title("마나토끼 멀티스레드 크롤러")
root.geometry("700x500")

# --- Top Frame ---
top_frame = ttk.Frame(root)
top_frame.pack(pady=5, padx=10, fill='x', expand=False)

# URL Input
url_label = ttk.Label(top_frame, text="URL:")
url_label.pack(side='left', padx=(0, 5))
url_entry = ttk.Entry(top_frame)
url_entry.pack(side='left', fill='x', expand=True)

# --- Download Path Frame ---
path_frame = ttk.Frame(root)
path_frame.pack(pady=5, padx=10, fill='x', expand=False)

path_label = ttk.Label(path_frame, text="다운로드 경로:")
path_label.pack(side='left', padx=(0, 5))
download_path_entry = ttk.Entry(path_frame)
download_path_entry.pack(side='left', fill='x', expand=True)
browse_button = ttk.Button(path_frame, text="찾아보기...", command=browse_directory)
browse_button.pack(side='left', padx=(5, 0))

# --- Control Frame ---
control_frame = ttk.Frame(root)
control_frame.pack(pady=5, padx=10, fill='x', expand=False)

# URL Type
url_type_label = ttk.Label(control_frame, text="URL TYPE:")
url_type_label.pack(side='left', padx=(0, 5))
url_type = tk.StringVar(value="목록")
radio_single = ttk.Radiobutton(control_frame, text="단편", variable=url_type, value="단편", state=tk.DISABLED)
radio_single.pack(side='left', padx=5)
radio_list = ttk.Radiobutton(control_frame, text="목록", variable=url_type, value="목록")
radio_list.pack(side='left', padx=5)

# Spacer
spacer = ttk.Label(control_frame, text="")
spacer.pack(side='left', padx=10)

# Num Threads
num_threads_label = ttk.Label(control_frame, text="스레드 개수:")
num_threads_label.pack(side='left', padx=(0, 5))
num_threads_entry = ttk.Entry(control_frame, width=5)
num_threads_entry.pack(side='left')
num_threads_entry.insert(0, "3")  # Default value

# --- Button Frame ---
button_frame = ttk.Frame(root)
button_frame.pack(pady=5, padx=10, fill='x', expand=False)

start_button = ttk.Button(button_frame, text="시작", command=start_crawling)
start_button.pack(side='left', padx=5)
stop_button = ttk.Button(button_frame, text="중지", command=stop_crawling, state=tk.DISABLED)
stop_button.pack(side='left', padx=(0, 5))

# --- Log Frame ---
log_frame = ttk.Frame(root)
log_frame.pack(pady=10, padx=10, fill='both', expand=True)
log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
log_text.pack(fill='both', expand=True)

# --- Progress Bar ---
progress_bar = ttk.Progressbar(root, orient='horizontal', length=100, mode='determinate')
progress_bar.pack(pady=10, padx=10, fill='x', expand=False)

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
