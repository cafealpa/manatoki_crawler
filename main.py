import threading
import tkinter as tk
from tkinter import messagebox

from crawler import master_crawl_thread, stop_event
# 각 모듈에서 필요한 클래스와 함수를 명확하게 임포트합니다.
from gui import CrawlerApp


class MainApplication:
    def __init__(self, root):
        self.root = root
        self.master_thread = None
        # CrawlerApp에 on_closing 메서드를 콜백으로 전달합니다.
        self.app = CrawlerApp(self.root, self.start_crawling, self.stop_crawling, self.on_closing)

    def start_crawling(self):
        # get_params()는 CrawlerApp의 메서드여야 합니다.
        params = self.app.get_params()
        if not params['target_url']:
            messagebox.showerror("오류", "URL을 입력하세요.")
            return

        try:
            num_threads = int(params['num_threads'])
            if not 1 <= num_threads <= 4:
                raise ValueError()
        except (ValueError, TypeError):
            messagebox.showerror("오류", "스레드 개수는 1에서 4 사이의 숫자여야 합니다.")
            return

        # GUI 상태 업데이트는 GUI 큐를 통해 처리하는 것이 더 안전하지만,
        # 시작 시점에서는 직접 제어할 수 있습니다.
        self.app.set_ui_state('start')

        self.app.log("=" * 800)

        # master_crawl_thread에 인자를 올바르게 전달합니다.
        # (이전 논의를 바탕으로 params 딕셔너리와 app의 gui_queue를 전달)
        args = (params, self.app.gui_queue)
        self.master_thread = threading.Thread(target=master_crawl_thread, args=args)
        self.master_thread.daemon = True
        self.master_thread.start()

    def stop_crawling(self):
        if self.master_thread and self.master_thread.is_alive():
            # 로그 기록은 GUI 큐를 통해 안전하게 처리합니다.
            self.app.log("크롤링 중지를 요청했습니다...")
            stop_event.set()

    def on_closing(self):
        """
        애플리케이션의 모든 종료 로직을 책임지는 메서드.
        """
        if messagebox.askokcancel("종료", "마나토끼 수집기를 종료하시겠습니까?"):
            # 1. 백그라운드 스레드에게 중지 신호를 보냅니다.
            stop_event.set()
            # 2. 스레드가 실행 중이라면, 완전히 끝날 때까지 기다립니다.
            if self.master_thread and self.master_thread.is_alive():
                self.app.log("백그라운드 작업이 끝날 때까지 기다리는 중...")
                self.master_thread.join()

            # 3. 모든 것이 안전하게 정리된 후, GUI를 파괴합니다.
            self.root.destroy()

    def run(self):
        # 이제 메인 루프는 숨겨진 root 창에서 실행됩니다.
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 메인 윈도우는 숨깁니다. CrawlerApp이 Toplevel로 표시됩니다.
    app = MainApplication(root)
    app.run()
