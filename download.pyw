import os, ssl, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.request import urlopen, Request

ssl_context = ssl.create_default_context()
ssl_context.check_hostname, ssl_context.verify_mode = False, ssl.CERT_NONE

ISO_DATA = {
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
        self.root.geometry("440x300")
        self.root.resizable(False, False)
        
      
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.download_dir = tk.StringVar(value=script_dir)
        
        self.active_download = None
        self.cancel_requested = False
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
        threading.Thread(target=self.download_file, args=(name, url), daemon=True).start()

    def download_file(self, name, url):
        fn = url.split("?")[0].split("/")[-1]
        save_dir = self.download_dir.get()
        
        
        os.makedirs(save_dir, exist_ok=True)
        
        save_path = os.path.join(save_dir, fn if fn.endswith(".iso") else f"{name.lower().replace(' ', '_')}.iso")
        self.lbl_status.config(text=f"Connecting: {name}")
        self.progress["value"] = 0
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        try:
            with urlopen(req, context=ssl_context) as resp, open(save_path, "wb") as out:
                total, done = int(resp.headers.get("Content-Length", 0)), 0
                while buf := resp.read(131072):
                    if self.cancel_requested:
                        break
                    done += len(buf)
                    out.write(buf)
                    if total > 0:
                        pct = (done / total) * 100
                        self.progress["value"] = pct
                        self.lbl_status.config(text=f"{name}: {pct:.1f}% ({done//1048576}/{total//1048576} MB)")

            if self.cancel_requested:
                if os.path.exists(save_path): os.remove(save_path)
                self.lbl_status.config(text="Download cancelled.")
                self.progress["value"] = 0
            else:
                self.lbl_status.config(text="Completed!")
                messagebox.showinfo("Success", f"{os.path.basename(save_path)} downloaded successfully.")

        except Exception as e:
            self.lbl_status.config(text="An error occurred!")
            messagebox.showerror("Error", str(e))
        finally:
            self.active_download = None
            self.cancel_requested = False
            self.set_other_buttons_state(name, "normal")
            self.download_buttons[name].config(text="Download", bg="#16a34a")

def open_iso_downloader(parent=None):
    win = tk.Toplevel(parent) if parent else tk.Tk()
    app = ISODownloaderApp(win)
    if not parent: win.mainloop()

if __name__ == "__main__":
    open_iso_downloader()
