import threading
import tkinter as tk
from tkinter import messagebox

from gui import CrawlerApp
from crawler import master_crawl_thread, stop_event

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.master_thread = None
        self.app = CrawlerApp(self.start_crawling, self.stop_crawling)

    def start_crawling(self):
        params = self.app.get_params()
        if not params['target_url']:
            messagebox.showerror("오류", "URL을 입력하세요.")
            return

        try:
            if not 1 <= params['num_threads'] <= 10:
                raise ValueError()
        except ValueError:
            messagebox.showerror("오류", "스레드 개수는 1에서 10 사이의 숫자여야 합니다.")
            return

        self.app.start_button.config(state=tk.DISABLED)
        self.app.stop_button.config(state=tk.NORMAL)
        self.app.progress_bar['value'] = 0

        self.master_thread = threading.Thread(target=master_crawl_thread, args=(params,))
        self.master_thread.daemon = True
        self.master_thread.start()

    def stop_crawling(self):
        if self.master_thread and self.master_thread.is_alive():
            self.app.log("크롤링 중지를 요청했습니다...")
            stop_event.set()

    def run(self):
        self.app.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    app = MainApplication(root)
    app.run()