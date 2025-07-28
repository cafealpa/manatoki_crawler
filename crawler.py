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


def crawl_manatoki():
    if not os.path.exists("download_mana"):
        os.makedirs("download_mana")
        print("Created download_mana directory")

    driver = Driver(uc=True)  # uc=True for undetected_chromedriver
    try:
        driver.get(TARGET_URL)
        print(f"Successfully opened {TARGET_URL}")

        # 페이지 로딩 후 랜덤 스크롤 (300px ~ 800px)
        scroll_amount = random.randint(300, 800)
        print(f"페이지 로딩 후 {scroll_amount}px 스크롤합니다.")
        driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_amount)

        # 페이지 가장 아래까지 스크롤하여 모든 이미지 로딩
        print("페이지 가장 아래까지 스크롤합니다.")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # 스크롤 후 컨텐츠 로딩을 위한 대기

        # <article itemprop="articleBody"> 요소가 로딩될 때까지 대기

        # <article itemprop="articleBody"> 요소가 로딩될 때까지 대기
        print("Waiting for <article itemprop=\"articleBody\"> to load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
        )
        print("<article itemprop=\"articleBody\"> loaded.")

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

            # 각 아티클 URL 순회
            for url in article_urls:
                if is_url_crawled(url):
                    print(f"이미 크롤링된 URL입니다: {url}")
                    continue

                print(f"Navigating to: {url}")
                driver.get(url)

                # 캡챠 감지 및 대기
                # try:
                #     # 캡챠 페이지에 흔히 나타나는 텍스트나 요소로 감지
                #     WebDriverWait(driver, 2).until(
                #         EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '로봇이 아닙니다')] | //*[contains(text(), 'CAPTCHA')] | //*[@id='recaptcha-challenge']"))
                #     )
                #     print("CAPTCHA detected! Please solve the CAPTCHA in the browser and press Enter to continue...")
                #     input("Press Enter after solving CAPTCHA...")
                #     print("Continuing...")
                # except:
                #     print("No CAPTCHA detected or timed out.")

                # 페이지 가장 아래까지 스크롤하여 모든 이미지 로딩
                # print("페이지 가장 아래까지 스크롤합니다.")
                # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # time.sleep(2)

                # 페이지의 body 요소를 선택
                body = driver.find_element(By.TAG_NAME, "body")

                # 방법 A: Page Down 키를 눌러 한 화면씩 스크롤
                for _ in range(30):
                    body.send_keys(Keys.PAGE_DOWN)
                    time.sleep(0.1)

                # 방법 B: End 키를 눌러 페이지 맨 아래로 한 번에 이동
                # body.send_keys(Keys.END)

                # 방법 C: 화살표 아래 키를 눌러 조금씩 스크롤
                # body.send_keys(Keys.ARROW_DOWN)

                # 페이지 로딩 후 이미지 비동기 로딩 1초 대기
                time.sleep(1)

                # 페이지 소스 다시 가져오기 (캡챠 해결 후)
                page_source = driver.page_source

                # 스크롤 후 컨텐츠 로딩을 위한 대기
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
                            # 상대 경로인 경우 절대 경로로 변환 (필요시)
                            # if img_url.startswith('//'):
                            #     img_url = "https:" + img_url
                            # elif img_url.startswith('/'):
                            #     # 현재 페이지 URL을 기반으로 절대 경로 생성 (복잡할 수 있으므로 주의)
                            #     # 여기서는 간단히 처리하고, 필요시 urljoin 사용 고려
                            #     pass  # TODO: 상대 경로 처리 로직 추가

                            if '.gif' in img_url.lower():
                                print(f"Skipping GIF image: {img_url}")
                                continue

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

                                # GIF 이미지인 경우 다운로드 건너뛰기
                                # if ext.lower() == '.gif' or '.gif' in img_url.lower():
                                #     print(f"Skipping GIF image: {img_url}")
                                #     continue

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
                    print("html_mana_section not found.")

                add_crawled_url(url)

                # 다음 페이지로 이동하기 전에 랜덤 대기 (1초 ~ 9초)
                wait_time = random.randint(1, 9)
                print(f"다음 페이지로 이동하기 전 {wait_time}초 대기합니다.")
                time.sleep(wait_time)

        else:
            print("articleBody not found.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()


def get_target_pages(driver: Driver) -> list:
    try:
        driver.get(TARGET_URL)
        print(f"Successfully opened {TARGET_URL}")

        # <article itemprop="articleBody"> 요소가 로딩될 때까지 대기
        print("Waiting for <article itemprop=\"articleBody\"> to load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article[itemprop='articleBody']"))
        )
        print("<article itemprop=\"articleBody\"> loaded.")

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


if __name__ == "__main__":
    crawl_manatoki()
