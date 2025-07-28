import mimetypes
import os
import random
import time

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from config import TARGET_URL
from database import is_url_crawled, add_crawled_url


def crawl_mana_page(driver, article_urls):
    for url in article_urls:
        # 기존 크롤링 여부 확인
        if is_url_crawled(url):
            print(f"이미 크롤링된 URL입니다: {url}")
            continue

        # 페이지 이동
        print(f"Navigating to: {url}")
        driver.get(url)

        # 페이지의 body 요소를 선택
        body = driver.find_element(By.TAG_NAME, "body")

        # 방법 A: Page Down 키를 눌러 한 화면씩 스크롤
        for _ in range(30):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.1)

        # 페이지 로딩 후 이미지 비동기 로딩 1초 대기
        # time.sleep(1)

        # 페이지 소스 다시 가져오기
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # 게시물 제목 추출 (폴더 이름으로 사용)
        # Manatoki 페이지 구조에 따라 h1 또는 다른 클래스의 div에서 제목을 찾을 수 있습니다.
        # 여기서는 h1 태그를 먼저 시도하고, 없으면 view-title 클래스를 가진 div를 시도합니다.
        title_element = soup.find('h1')
        if not title_element:
            title_element = soup.find('div', class_='view-title')  # 예시: 실제 클래스명 확인 필요

        if title_element:
            post_title = title_element.get_text(strip=True)
            # 파일 시스템에 안전한 이름으로 변환
            post_title = "".join(c for c in post_title if c.isalnum() or c in (' ', '.', '_')).rstrip()
            print(f"Post Title: {post_title}")
        else:
            post_title = "untitled_post"
            print("Could not find post title. Using default name.")

        # 이미지 저장 폴더 생성
        if not os.path.exists("download_mana"):
            os.makedirs("download_mana")

        if not os.path.exists(os.path.join("download_mana", post_title)):
            os.makedirs(os.path.join("download_mana", post_title))
            print(f"Created directory: {os.path.join('download_mana', post_title)}")

        # 이미지 다운로드
        html_mana_section = soup.find('section', itemtype='http://schema.org/NewsArticle')
        if html_mana_section:
            img_tags = html_mana_section.find_all('img')
            print(f"Found {len(img_tags)} images.")

            for i, img in enumerate(img_tags):
                img_url = img.get('src')
                print(f"img url:{img_url}")

                if img_url:

                    # gif 확장자가 url에 있으면 skip
                    if '.gif' in img_url.lower():
                        print(f"Skipping GIF image: {img_url}")
                        continue

                    # 이미지 다운로드
                    try:
                        header = {'referer': 'https://manatoki468.net/'}
                        response = requests.get(img_url, stream=True, headers=header)
                        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생

                        # 파일 확장자 추출
                        content_type = response.headers.get('Content-Type')
                        if content_type:
                            ext = mimetypes.guess_extension(content_type)
                            if not ext:  # guess_extension이 실패할 경우 URL에서 추출 시도
                                ext = os.path.splitext(img_url)[1]
                        else:
                            ext = os.path.splitext(img_url)[1]
                        if not ext:  # 확장자가 없는 경우 기본값
                            ext = ".jpg"

                        img_filename = os.path.join("download_mana", post_title, f"{i + 1}{ext}")
                        with open(img_filename, 'wb') as f:
                            for chunk in response.iter_content(1024):
                                f.write(chunk)
                        print(f"Downloaded {img_filename}")

                    except requests.exceptions.RequestException as req_err:
                        print(f"Error downloading {img_url}: {req_err}")
                    except Exception as err:
                        print(f"An unexpected error occurred while downloading {img_url}: {err}")

                else:
                    print(f"img_url is None: {img_url}")

            # 페이지 크롤링이 완료되었을 경우만 DB에 url 추가
            add_crawled_url(url, title_element)
        else:
            print("html_mana_section not found.")

        # 다음 페이지로 이동하기 전에 랜덤 대기 (1초 ~ 9초)
        wait_time = random.randint(1, 9)
        print(f"다음 페이지로 이동하기 전 {wait_time}초 대기합니다.")
        time.sleep(wait_time)

# 목록 조회
def get_target_pages(driver: Driver) -> list:
    """
        지정된 웹 페이지에서 대상 기사 URL을 추출합니다.

        이 기능은 제공된 웹 드라이버를 사용하여 지정된 `TARGET_URL`로 이동한 후
        대상 웹 페이지의 본문 내용을 포함하는 HTML 기사 요소가 로드될 때까지 대기합니다.
        로드가 완료되면 콘텐츠를 파싱하여 지정된 ‘serial-list’ 섹션에 포함된 연속 URL 목록을
        추출합니다.

        :param driver: 웹 페이지를 탐색하는 데 사용되는 Selenium WebDriver 인스턴스.
        :type driver: Driver
        :return: 기사 본문의 ‘serial-list’ 섹션에 포함된 URL 목록 또는 해당 URL이 발견되지 않은 경우 빈 목록.
        :rtype: list
    """
    try:
        driver.get(TARGET_URL)
        print(f"Successfully opened {TARGET_URL}")

        # <article itemprop="articleBody"> 요소가 로딩될 때까지 대기
        print("Waiting for <article itemprop='articleBody'> to load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
        )
        print("<article itemprop='articleBody'> loaded.")

        # 페이지 소스 가져오기
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # articleBody 내의 연재 목록 URL 수집
        article_body = soup.find('article', itemprop='articleBody')
        if article_body:
            print("Found articleBody. Extracting URLs...")
            serial_list_div = article_body.find('div', class_='serial-list')
            if serial_list_div:
                links = serial_list_div.find_all('a', href=True)
            else:
                links = []
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

def crawl_manatoki():
    # 다운로드 폴더 생성
    if not os.path.exists("download_mana"):
        os.makedirs("download_mana")
        print("Created download_mana directory")

    driver = Driver(uc=True)  # uc=True for undetected_chromedriver
    try:
        # 목록 조회
        article_target_list = get_target_pages(driver)
        # 조회된 목록으로 크롤링 실행
        crawl_mana_page(driver, article_target_list)

    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_manatoki()
