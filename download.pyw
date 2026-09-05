import os, time, threading, subprocess, shutil
import urllib.request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ISO_DATA = {
    "Debian KDE": "https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/debian-live-13.6.0-amd64-kde.iso",
    "CachyOS": "https://cdn77.cachyos.org/ISO/desktop/260628/cachyos-desktop-linux-260628.iso",
    "Arch Linux": "https://arch-mirror.brightlight.today/iso/2026.07.01/archlinux-2026.07.01-x86_64.iso",
    "Ubuntu Desktop": "https://releases.ubuntu.com/26.04/ubuntu-26.04-desktop-amd64.iso",
    "Fedora KDE": "https://download.fedoraproject.org/pub/fedora/linux/releases/44/KDE/x86_64/iso/Fedora-KDE-Desktop-Live-44-1.7.x86_64.iso",
    "Linux Mint Cinnamon": "https://ftp.linux.org.tr/linuxmint/iso/stable/22.3/linuxmint-22.3-cinnamon-64bit.iso"
}

class ISODownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ISO Downloader")
        self.root.geometry("440x330")
        self.root.resizable(False, False)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.download_dir = tk.StringVar(value=script_dir)

        self.active_download = None
        self.cancel_requested = False
        self.process = None
        self.download_buttons = {}
        self.create_widgets()

    def create_widgets(self):
        f_dir = tk.Frame(self.root, padx=10, pady=5)
        f_dir.pack(fill="x")
        tk.Entry(f_dir, textvariable=self.download_dir, state="readonly", width=36).pack(side="left", padx=(0, 5))
        tk.Button(f_dir, text="Browse", command=self.browse_folder).pack(side="right")

        f_list = tk.LabelFrame(self.root, text=" Available ISO List ", padx=8, pady=5)
        f_list.pack(fill="both", expand=True, padx=10, pady=2)

        for name, url in ISO_DATA.items():
            row = tk.Frame(f_list)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=name, font=("Segoe UI", 9), anchor="w").pack(side="left")
            btn = tk.Button(row, text="Download", bg="#16a34a", fg="white", font=("Segoe UI", 8, "bold"), width=8,
                            command=lambda n=name, u=url: self.handle_click(n, u))
            btn.pack(side="right")
            self.download_buttons[name] = btn

        f_prog = tk.Frame(self.root, padx=10, pady=5)
        f_prog.pack(fill="x")
        self.lbl_status = tk.Label(f_prog, text="Ready", anchor="w", font=("Segoe UI", 8, "italic"))
        self.lbl_status.pack(fill="x")
        self.progress = ttk.Progressbar(f_prog, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=2)

    def browse_folder(self):
        if sel := filedialog.askdirectory(initialdir=self.download_dir.get()):
            self.download_dir.set(sel)

    def handle_click(self, name, url):
        if self.active_download == name:
            self.cancel_requested = True
            self.lbl_status.config(text="Cancelling...")
            if self.process:
                self.process.terminate()
        elif not self.active_download:
            self.start_download(name, url)

    def set_other_buttons_state(self, active_name, state):
        for btn_name, btn in self.download_buttons.items():
            if btn_name != active_name: btn.config(state=state)

    def start_download(self, name, url):
        self.active_download = name
        self.cancel_requested = False
        self.set_other_buttons_state(name, "disabled")
        self.download_buttons[name].config(text="Cancel", bg="#dc2626")
        threading.Thread(target=self.download_file_robust, args=(name, url), daemon=True).start()

    def get_remote_file_size(self, url):
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                length = resp.headers.get('content-length')
                return int(length) if length else 0
        except:
            return 0

    def download_file_robust(self, name, url):
        fn = url.split("?")[0].split("/")[-1]
        save_dir = self.download_dir.get()
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, fn if fn.endswith(".iso") else f"{name.lower().replace(' ', '_')}.iso")

        self.root.after(0, lambda: self.lbl_status.config(text=f"Connecting: {name}"))
        self.root.after(0, lambda: self.progress.config(value=0))


        total_size = self.get_remote_file_size(url)


        env = os.environ.copy()
        env.pop('LD_LIBRARY_PATH', None)


        if shutil.which("curl"):
            cmd = ["curl", "-L", "-k", "-s", "-o", save_path, url]
        elif shutil.which("wget"):
            cmd = ["wget", "--no-check-certificate", "-q", "-O", save_path, url]
        else:
            self.root.after(0, lambda: messagebox.showerror("Error", "Neither curl nor wget was found on the system."))
            self.root.after(0, lambda: self._reset_ui(name))
            return

        try:

            self.process = subprocess.Popen(cmd, env=env)


            while self.process.poll() is None:
                if self.cancel_requested:
                    self.process.terminate()
                    break

                if os.path.exists(save_path) and total_size > 0:
                    current_size = os.path.getsize(save_path)
                    pct = min((current_size / total_size) * 100, 99.9)
                    self.root.after(0, self._update_progress, name, pct)

                time.sleep(0.3)

            if self.cancel_requested:
                if os.path.exists(save_path): os.remove(save_path)
                self.root.after(0, lambda: self.lbl_status.config(text="Download cancelled."))
                self.root.after(0, lambda: self.progress.config(value=0))
            elif self.process.returncode == 0:
                self.root.after(0, lambda: self.progress.config(value=100))
                self.root.after(0, lambda: self.lbl_status.config(text="Completed!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"{os.path.basename(save_path)} downloaded successfully."))
            else:
                raise Exception(f"Download process failed with exit code {self.process.returncode}")

        except Exception as e:
            if not self.cancel_requested:
                if os.path.exists(save_path): os.remove(save_path)
                self.root.after(0, lambda: self.lbl_status.config(text="An error occurred!"))
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self._reset_ui(name))

    def _update_progress(self, name, pct):
        self.progress["value"] = pct
        self.lbl_status.config(text=f"{name}: {pct:.1f}%")

    def _reset_ui(self, name):
        self.active_download = None
        self.process = None
        self.cancel_requested = False
        self.set_other_buttons_state(name, "normal")
        self.download_buttons[name].config(text="Download", bg="#16a34a")

def open_iso_downloader(parent=None):
    win = tk.Toplevel(parent) if parent else tk.Tk()
    app = ISODownloaderApp(win)
    if not parent: win.mainloop()

if __name__ == "__main__":
    open_iso_downloader()
