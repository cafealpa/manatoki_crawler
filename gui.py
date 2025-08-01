import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

class CrawlerApp(tk.Tk):
    def __init__(self, start_callback, stop_callback):
        super().__init__()
        self.start_callback = start_callback
        self.stop_callback = stop_callback

        self.title("마나토끼 멀티스레드 크롤러")
        self.geometry("700x500")

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        # --- Menu Bar ---
        menu_bar = tk.Menu(self)
        etc_menu = tk.Menu(menu_bar, tearoff=0)
        etc_menu.add_command(label="버전확인", command=self.show_version)
        menu_bar.add_cascade(label="기타", menu=etc_menu)
        self.config(menu=menu_bar)

        # --- Top Frame ---
        top_frame = ttk.Frame(self)
        top_frame.pack(pady=5, padx=10, fill='x', expand=False)

        url_label = ttk.Label(top_frame, text="URL:")
        url_label.pack(side='left', padx=(0, 5))
        self.url_entry = ttk.Entry(top_frame)
        self.url_entry.pack(side='left', fill='x', expand=True)

        # --- Download Path Frame ---
        path_frame = ttk.Frame(self)
        path_frame.pack(pady=5, padx=10, fill='x', expand=False)

        path_label = ttk.Label(path_frame, text="다운로드 경로:")
        path_label.pack(side='left', padx=(0, 5))
        self.download_path_entry = ttk.Entry(path_frame)
        self.download_path_entry.pack(side='left', fill='x', expand=True)
        browse_button = ttk.Button(path_frame, text="찾아보기...", command=self.browse_directory)
        browse_button.pack(side='left', padx=(5, 0))

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

    def show_version(self):
        messagebox.showinfo("버전 정보", "마나토끼 멀티스레드 크롤러 v1.0")

    def on_closing(self):
        if messagebox.askokcancel("종료", "크롤러를 종료하시겠습니까?"):
            self.stop_callback()
            self.destroy()

    def get_params(self):
        return {
            'target_url': self.url_entry.get(),
            'download_path': self.download_path_entry.get(),
            'num_threads': int(self.num_threads_entry.get()),
            'log_callback': self.log,
            'update_progress_callback': self.update_progress,
            'on_complete_callback': self.on_crawl_complete
        }

    def update_progress(self, value):
        self.progress_bar['value'] = value
        self.update_idletasks()

    def on_crawl_complete(self, success):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
