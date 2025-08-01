import threading
import tkinter as tk
from tkinter import messagebox

from crawler import master_crawl_thread
from gui import CrawlerApp


class MainApplication:
    def __init__(self, root):
        self.root = root
        self.master_thread = None
        self.stop_event = threading.Event()
        self.app = CrawlerApp(self.root, self.start_crawling, self.stop_crawling, self.on_closing)

    def start_crawling(self):
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

        self.app.set_ui_state('start')
        self.app.log("=" * 90)

        self.stop_event.clear()

        args = (params, self.app.gui_queue, self.stop_event)
        self.master_thread = threading.Thread(target=master_crawl_thread, args=args)
        self.master_thread.daemon = True
        self.master_thread.start()

    def stop_crawling(self):
        if self.master_thread and self.master_thread.is_alive():
            self.app.log("크롤링 중지를 요청했습니다...")
            self.stop_event.set()

    def on_closing(self):
        """
        애플리케이션의 모든 종료 로직을 책임지는 메서드.
        """
        if messagebox.askokcancel("종료", "마나토끼 수집기를 종료하시겠습니까?"):
            self.stop_event.set()
            if self.master_thread and self.master_thread.is_alive():
                self.app.log("백그라운드 작업이 끝날 때까지 기다리는 중...")
                self.master_thread.join()

            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = MainApplication(root)
    app.run()
