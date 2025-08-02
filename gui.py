import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import os
import queue
from db_viewer import DBViewer

class CrawlerApp(tk.Toplevel):
    def __init__(self, master, start_callback, stop_callback, on_close_callback):
        super().__init__(master)
        self.title("마나토끼 수집기")
        self.geometry("700x500")

        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.gui_queue = queue.Queue()

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", on_close_callback)
        self.process_queue()

    def _create_widgets(self):
        # --- Menu Bar ---
        menu_bar = tk.Menu(self)
        tool_menu = tk.Menu(menu_bar, tearoff=0)
        tool_menu.add_command(label="DB 확인", command=self.open_db_viewer)
        menu_bar.add_cascade(label="도구", menu=tool_menu)

        etc_menu = tk.Menu(menu_bar, tearoff=0)
        etc_menu.add_command(label="버전확인", command=self.show_version)
        menu_bar.add_cascade(label="기타", menu=etc_menu)
        self.config(menu=menu_bar)

        # --- Download Path Frame ---
        path_frame = ttk.Frame(self)
        path_frame.pack(pady=5, padx=10, fill='x', expand=False)

        path_label = ttk.Label(path_frame, text="다운로드 경로:")
        path_label.pack(side='left', padx=(0, 5))
        self.download_path_entry = ttk.Entry(path_frame)
        self.download_path_entry.pack(side='left', fill='x', expand=True)
        self.browse_button = ttk.Button(path_frame, text="찾아보기...", command=self.browse_directory)
        self.browse_button.pack(side='left', padx=(5, 0))

        # --- Top Frame ---
        top_frame = ttk.Frame(self)
        top_frame.pack(pady=5, padx=10, fill='x', expand=False)

        url_label = ttk.Label(top_frame, text="URL:")
        url_label.pack(side='left', padx=(0, 5))
        self.url_entry = ttk.Entry(top_frame)
        self.url_entry.pack(side='left', fill='x', expand=True)

        # --- Control Frame ---
        control_frame = ttk.Frame(self)
        control_frame.pack(pady=5, padx=10, fill='x', expand=False)

        url_type_label = ttk.Label(control_frame, text="URL TYPE:")
        url_type_label.pack(side='left', padx=(0, 5))
        self.url_type = tk.StringVar(value="목록")
        radio_single = ttk.Radiobutton(control_frame, text="단편", variable=self.url_type, value="단편", state=tk.DISABLED)
        radio_single.pack(side='left', padx=5)
        radio_list = ttk.Radiobutton(control_frame, text="목록", variable=self.url_type, value="목록")
        radio_list.pack(side='left', padx=5)

        spacer = ttk.Label(control_frame, text="")
        spacer.pack(side='left', padx=10)

        num_threads_label = ttk.Label(control_frame, text="스레드 개수:")
        num_threads_label.pack(side='left', padx=(0, 5))
        self.num_threads_entry = ttk.Entry(control_frame, width=5)
        self.num_threads_entry.pack(side='left')
        self.num_threads_entry.insert(0, "3")

        # --- Button Frame ---
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=5, padx=10, fill='x', expand=False)

        self.start_button = ttk.Button(button_frame, text="시작", command=self.start_callback)
        self.start_button.pack(side='left', padx=5)
        self.stop_button = ttk.Button(button_frame, text="중지", command=self.stop_callback, state=tk.DISABLED)
        self.stop_button.pack(side='left', padx=(0, 5))

        # --- Log Frame ---
        log_frame = ttk.Frame(self)
        log_frame.pack(pady=10, padx=10, fill='both', expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill='both', expand=True)

        # --- Progress Bar ---
        self.progress_bar = ttk.Progressbar(self, orient='horizontal', length=100, mode='determinate')
        self.progress_bar.pack(pady=10, padx=10, fill='x', expand=False)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.update_idletasks()

    def browse_directory(self):
        path = filedialog.askdirectory()
        if path:
            self.download_path_entry.delete(0, tk.END)
            self.download_path_entry.insert(0, path)
            list_url_path = os.path.join(path, "list_url.txt")
            if os.path.exists(list_url_path):
                try:
                    with open(list_url_path, 'r', encoding='utf-8') as f:
                        url = f.read().strip()
                        if url:
                            self.url_entry.delete(0, tk.END)
                            self.url_entry.insert(0, url)
                except Exception as e:
                    self.log(f"'list_url.txt' 파일 읽기 오류: {e}")

    def show_version(self):
        messagebox.showinfo("버전 정보", "마나토끼 마나토끼 수집기 v1.1.0")

    def open_db_viewer(self):
        DBViewer(self)

    def get_params(self):
        """UI에서 파라미터를 가져와 딕셔너리로 반환합니다."""
        return {
            'target_url': self.url_entry.get(),
            'download_path': self.download_path_entry.get(),
            'num_threads': self.num_threads_entry.get(),
        }

    def update_progress(self, value):
        self.progress_bar['value'] = value
        self.update_idletasks()

    def set_ui_state(self, state):
        """UI 컨트롤의 상태를 변경합니다 (예: 버튼 활성화/비활성화)"""
        if state == 'start':
            self.download_path_entry.config(state=tk.DISABLED)
            self.browse_button.config(state=tk.DISABLED)
            self.url_entry.config(state=tk.DISABLED)
            self.num_threads_entry.config(state=tk.DISABLED)
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

        elif state == 'stop':
            self.download_path_entry.config(state=tk.NORMAL)
            self.browse_button.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.NORMAL)
            self.num_threads_entry.config(state=tk.NORMAL)
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def process_queue(self):
        """GUI 큐를 주기적으로 확인하고 모든 메시지를 처리합니다."""
        try:
            while not self.gui_queue.empty():
                msg_type, data = self.gui_queue.get_nowait()
                if msg_type == 'log':
                    self.log(data)
                elif msg_type == 'progress':
                    self.update_progress(data)
                elif msg_type == 'complete':
                    self.set_ui_state('stop')
                elif msg_type == 'show_info':
                    messagebox.showinfo("알림", data)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)
