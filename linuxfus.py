#!/usr/bin/env python3
import os
import sys
import subprocess
import threading
import shutil
import time
import json
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

cancel_requested = False
iso_action_mode = "select"
current_lang = "tr"
translations = {}

def is_root():
    return os.geteuid() == 0

def get_asset_path(relative_path):
    appimage_assets = os.environ.get("APPIMAGE_ASSETS_DIR")
    if appimage_assets and os.path.exists(os.path.join(appimage_assets, relative_path)):
        return os.path.join(appimage_assets, relative_path)

    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_available_languages():
    locales_dir = get_asset_path("locales")
    if not os.path.exists(locales_dir):
        locales_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

    langs = []
    if os.path.exists(locales_dir):
        for file in os.listdir(locales_dir):
            if file.endswith(".json"):
                langs.append(os.path.splitext(file)[0])
    return sorted(langs) if langs else ["tr", "en", "de"]

def load_translations(lang):
    global translations
    lang_file = get_asset_path(f"locales/{lang}.json")
    if not os.path.exists(lang_file):
        lang_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"locales/{lang}.json")

    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                translations = json.load(f)
        except Exception:
            translations = {}
    else:
        translations = {}

def tr(key):
    return translations.get(key, key)

load_translations(current_lang)

if __name__ == "__main__" and not is_root():
    try:
        if "APPIMAGE" in os.environ:
            target_bin = os.environ["APPIMAGE"]
        elif hasattr(sys, '_MEIPASS'):
            target_bin = os.path.abspath(sys.argv[0])
        else:
            target_bin = sys.executable

        xauth = os.environ.get('XAUTHORITY', os.path.expanduser('~/.Xauthority'))
        display = os.environ.get('DISPLAY', ':0')

        cmd = [
            "pkexec",
            "env",
            f"DISPLAY={display}",
            f"XAUTHORITY={xauth}",
            target_bin
        ]

        if not hasattr(sys, '_MEIPASS') and "APPIMAGE" not in os.environ:
            cmd.append(os.path.abspath(__file__))

        cmd.extend(sys.argv[1:])

        subprocess.run(cmd, check=True)
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Permission Error", f"Failed to acquire root privileges or action was cancelled:\n{str(e)}")
    sys.exit(0)

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

def open_iso_downloader():
    downloader_script = get_asset_path("download.pyw")

    if not os.path.exists(downloader_script):
        downloader_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download.pyw")

    if os.path.exists(downloader_script):
        try:
            subprocess.Popen(["python3", downloader_script])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch ISO Downloader:\n{str(e)}")
    else:
        messagebox.showerror("Error", f"Could not find download.pyw at:\n{downloader_script}")

def patch_efi_data(binary_data, old_name="rufus", new_name="lfus_"):
    if len(old_name) != len(new_name):
        raise ValueError("Old and new folder names must be of equal length!")
    old_ascii, new_ascii = old_name.encode('ascii'), new_name.encode('ascii')
    old_utf16, new_utf16 = old_name.encode('utf-16le'), new_name.encode('utf-16le')
    return binary_data.replace(old_ascii, new_ascii).replace(old_utf16, new_utf16)

def force_unmount_leftovers(dev_node=None):
    mounts = ["/tmp/lfus_boot", "/tmp/lfus_data", "/tmp/lfus_iso"]
    for m in mounts:
        subprocess.run(["umount", "-f", "-l", m], capture_output=True)
    if dev_node:
        subprocess.run(f"umount -f -l {dev_node}* 2>/dev/null", shell=True, capture_output=True)

def calculate_iso_sha256(filepath, progress_callback=None):
    sha256 = hashlib.sha256()
    total_size = os.path.getsize(filepath)
    read_size = 0
    buffer_size = 4 * 1024 * 1024

    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(buffer_size)
            if not chunk:
                break
            sha256.update(chunk)
            read_size += len(chunk)
            if progress_callback:
                pct = int((read_size / total_size) * 100)
                progress_callback(pct)

    return sha256.hexdigest().lower()

app = tk.Tk()
app.title(tr("window_title"))
app.geometry("440x790")
app.resizable(False, False)

icon_path = get_asset_path("icon.png")
if os.path.exists(icon_path):
    try:
        app_icon = tk.PhotoImage(file=icon_path)
        app.iconphoto(False, app_icon)
    except Exception as e:
        pass

style = ttk.Style()
if 'clam' in style.theme_names():
    style.theme_use('clam')

def get_usb_drives():
    drives = []
    try:
        output = subprocess.check_output(
            ["lsblk", "-d", "-n", "-o", "NAME,SIZE,TRAN,MODEL"],
            text=True
        )
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3 and "usb" in parts[2].lower():
                dev_name = parts[0]
                size = parts[1]
                model = " ".join(parts[3:]) if len(parts) > 3 else "USB Drive"
                drives.append(f"/dev/{dev_name} - {model} ({size})")
    except Exception:
        pass

    if not drives:
        drives = ["No USB Drive Found!"]
    return drives

def refresh_drives():
    usb_list = get_usb_drives()
    drive_cb['values'] = usb_list
    drive_cb.current(0)

def set_iso_text(text):
    iso_entry.config(state="normal")
    iso_entry.delete(0, tk.END)
    iso_entry.insert(0, text)
    iso_entry.config(state="readonly")

def select_iso():
    file_path = filedialog.askopenfilename(
        title=tr("boot_selection"),
        filetypes=[("ISO Images", "*.iso"), ("All Files", "*.*")]
    )
    if file_path:
        set_iso_text(file_path)

        iso_filename = os.path.splitext(os.path.basename(file_path))[0]
        custom_label = iso_filename[:11].replace(" ", "_").upper()
        label_entry.delete(0, tk.END)
        label_entry.insert(0, custom_label if custom_label else "LINUXFUS")

def handle_iso_action():
    if iso_action_mode == "select":
        select_iso()
    else:
        open_iso_downloader()

def set_iso_mode(mode):
    global iso_action_mode
    iso_action_mode = mode
    if mode == "select":
        btn_iso_action.config(text=tr("browse"))
    else:
        btn_iso_action.config(text="INSTALL")

def show_iso_menu():
    iso_menu.post(btn_iso_arrow.winfo_rootx(), btn_iso_arrow.winfo_rooty() + btn_iso_arrow.winfo_height())

def update_progress(val, text=""):
    progress['value'] = val
    if text:
        status_label.config(text=text)
    app.update_idletasks()

def change_language(lang):
    global current_lang
    current_lang = lang
    load_translations(lang)

    app.title(tr("window_title"))
    lbl_device.config(text=tr("target_device"))
    btn_reset.config(text=tr("clean_usb"))
    btn_refresh.config(text=tr("refresh"))
    lbl_boot.config(text=tr("boot_selection"))
    lbl_hash.config(text=tr("sha_label"))
    btn_verify.config(text=tr("verify"))

    current_text = iso_entry.get()
    if current_text in ["Select an ISO file...", "Bir ISO dosyası seçin...", "ISO-Datei auswählen..."] or current_text == "":
        set_iso_text(tr("select_iso_placeholder"))

    btn_iso_action.config(text=tr("browse") if iso_action_mode == "select" else "INSTALL")
    lbl_partition.config(text=tr("partition_scheme"))
    lbl_fs.config(text=tr("target_fs"))
    lbl_label.config(text=tr("volume_label"))
    status_label.config(text=tr("status_ready"))
    btn_start.config(text=tr("start_write"))
    btn_cancel.config(text=tr("cancel"))
    dd_check.config(text=tr("dd_mode"))

    iso_menu.entryconfig(0, label=tr("menu_select"))
    iso_menu.entryconfig(1, label=tr("menu_download"))

def verify_sha_worker():
    iso_path = iso_entry.get().strip().strip('"').strip("'")
    expected_hash = hash_entry.get().strip().lower()

    if not os.path.exists(iso_path) or os.path.isdir(iso_path):
        messagebox.showerror("Hata", "Lütfen önce geçerli bir ISO dosyası seçin!")
        return

    if not expected_hash:
        messagebox.showwarning("Uyarı", "Lütfen karşılaştırılacak SHA-256 kodunu yapıştırın!")
        return

    status_label.config(text="SHA-256 hesaplanıyor, lütfen bekleyin...")
    btn_verify.config(state="disabled")

    try:
        calculated_hash = calculate_iso_sha256(
            iso_path,
            lambda pct: update_progress(pct, f"SHA-256 Hesaplanıyor... %{pct}")
        )

        if calculated_hash == expected_hash:
            update_progress(100, "SHA-256 Doğrulama Başarılı!")
            messagebox.showinfo("Bütünlük Doğrulandı", "SHA-256 Kodu Eşleşti! ISO dosyası orijinal ve hatasız.")
        else:
            update_progress(0, "SHA-256 Eşleşmedi!")
            messagebox.showerror("Bütünlük Hatası", f"SHA-256 Kodu EŞLEŞMEDİ!\n\nHesaplanan: {calculated_hash}\nBeklenen: {expected_hash}")
    except Exception as e:
        messagebox.showerror("Hata", f"Hash hesaplanırken bir sorun oluştu:\n{str(e)}")
    finally:
        btn_verify.config(state="normal")

def verify_sha_action():
    threading.Thread(target=verify_sha_worker, daemon=True).start()

def reset_usb_worker(selected_drive):
    try:
        dev_node = selected_drive.split()[0]
        update_progress(10, "Cleaning: Unmounting drive partitions...")

        force_unmount_leftovers(dev_node)
        time.sleep(1)

        update_progress(30, "Cleaning: Wiping filesystem signatures...")
        subprocess.run(["wipefs", "-a", "-f", dev_node], capture_output=True)
        time.sleep(1)

        update_progress(60, "Cleaning: Creating new MBR partition table...")
        subprocess.run(["parted", "-s", dev_node, "mklabel", "msdos"], check=True)
        subprocess.run(["parted", "-s", dev_node, "mkpart", "primary", "fat32", "1MiB", "100%"], check=True)

        subprocess.run(["partprobe", dev_node], capture_output=True)
        time.sleep(2)

        p1 = f"{dev_node}p1" if ("nvme" in dev_node or "mmcblk" in dev_node) else f"{dev_node}1"

        update_progress(85, "Cleaning: Formatting as FAT32...")
        subprocess.run(["mkfs.vfat", "-F32", "-n", "RESET_USB", p1], check=True)

        subprocess.run(["sync"])

        update_progress(100, "USB Reset Complete! Single FAT32 partition ready.")
        messagebox.showinfo("Success", "USB Drive successfully restored to factory defaults!")
    except Exception as e:
        status_label.config(text="Reset Failed!")
        messagebox.showerror("Error", f"Failed to reset drive:\n{str(e)}")
    finally:
        btn_start.config(state="normal")
        btn_reset.config(state="normal")
        btn_refresh.config(state="normal")

def reset_usb_action():
    selected_drive = drive_cb.get()
    if "No USB Drive Found!" in selected_drive:
        messagebox.showerror("Error", "Please select a valid USB drive to reset!")
        return

    confirm = messagebox.askyesno(
        "WARNING: RESTORE USB",
        f"This will completely WIPEOUT {selected_drive} and restore it to a single FAT32 volume.\n\nContinue?"
    )
    if not confirm:
        return

    btn_start.config(state="disabled")
    btn_reset.config(state="disabled")
    btn_refresh.config(state="disabled")

    threading.Thread(target=reset_usb_worker, args=(selected_drive,), daemon=True).start()

def cancel_process():
    global cancel_requested
    if messagebox.askyesno("Cancel", "Are you sure you want to cancel the writing process?"):
        cancel_requested = True
        status_label.config(text="Status: Cancelling immediately...")
        btn_cancel.config(state="disabled")
        app.update()

def get_dir_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def copy_with_progress(src, dst):
    global cancel_requested
    total_bytes = get_dir_size(src)
    copied_bytes = 0
    buffer_size = 4 * 1024 * 1024

    for root, dirs, files in os.walk(src):
        if cancel_requested:
            raise Exception("Operation cancelled by user.")

        rel_path = os.path.relpath(root, src)
        dest_dir = os.path.join(dst, rel_path) if rel_path != "." else dst
        os.makedirs(dest_dir, exist_ok=True)

        for f in files:
            if cancel_requested:
                raise Exception("Operation cancelled by user.")

            src_file = os.path.join(root, f)
            dst_file = os.path.join(dest_dir, f)

            with open(src_file, 'rb') as fsrc, open(dst_file, 'wb') as fdst:
                while True:
                    if cancel_requested:
                        raise Exception("Operation cancelled by user.")

                    buf = fsrc.read(buffer_size)
                    if not buf:
                        break

                    fdst.write(buf)
                    copied_bytes += len(buf)

                    pct = int((copied_bytes / total_bytes) * 100) if total_bytes > 0 else 0
                    update_progress(40 + int(pct * 0.5), f"4/5: Copying Files... {pct}%")

def copy_and_patch_assets(assets_dir, target_drive):
    global cancel_requested
    if os.path.exists(assets_dir):
        for root, dirs, files in os.walk(assets_dir):
            if cancel_requested:
                raise Exception("Operation cancelled by user.")
            rel_path = os.path.relpath(root, assets_dir)
            dest_dir = os.path.join(target_drive, rel_path) if rel_path != "." else target_drive
            os.makedirs(dest_dir, exist_ok=True)

            for f in files:
                if cancel_requested:
                    raise Exception("Operation cancelled by user.")
                src_file = os.path.join(root, f)
                dst_file = os.path.join(dest_dir, f)

                if f.lower().endswith(".efi"):
                    with open(src_file, "rb") as fsrc:
                        raw_data = fsrc.read()
                    patched_data = patch_efi_data(raw_data, "rufus", "lfus_")
                    with open(dst_file, "wb") as fdst:
                        fdst.write(patched_data)
                else:
                    shutil.copy2(src_file, dst_file)
    else:
        raise Exception("Critical Error: 'assets' folder not found!")

def write_iso_worker(selected_drive, iso_path):
    global cancel_requested
    mount_boot, mount_data, mount_iso = "/tmp/lfus_boot", "/tmp/lfus_data", "/tmp/lfus_iso"

    try:
        dev_node = selected_drive.split()[0]
        if dd_var.get():
            update_progress(10, "DD Mode: Cleaning lingering mounts...")
            force_unmount_leftovers(dev_node)
            time.sleep(1)

            if cancel_requested: raise Exception("Operation cancelled by user.")
            update_progress(30, "DD Mode: Writing raw ISO image...")
            total_size = os.path.getsize(iso_path)
            written = 0
            chunk_size = 4 * 1024 * 1024

            with open(iso_path, 'rb') as f_iso, open(dev_node, 'wb') as f_dev:
                while True:
                    if cancel_requested:
                        raise Exception("Operation cancelled by user.")
                    chunk = f_iso.read(chunk_size)
                    if not chunk:
                        break
                    f_dev.write(chunk)
                    written += len(chunk)
                    pct = int((written / total_size) * 100) if total_size > 0 else 0
                    update_progress(30 + int(pct * 0.6), f"DD Mode Writing... {pct}%")

            subprocess.run(["sync"])
            update_progress(100, "DD Mode Completed Successfully!")
            messagebox.showinfo("Success", "Raw DD Write Complete!")
            return

        custom_label = label_entry.get().strip().replace(" ", "_")
        custom_label = (custom_label if custom_label else "LINUXFUS")[:11]

        p1 = f"{dev_node}p1" if ("nvme" in dev_node or "mmcblk" in dev_node) else f"{dev_node}1"
        p2 = f"{dev_node}p2" if ("nvme" in dev_node or "mmcblk" in dev_node) else f"{dev_node}2"

        update_progress(5, "1/5: Cleaning lingering mounts...")
        force_unmount_leftovers(dev_node)
        time.sleep(1)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        subprocess.run(["wipefs", "-a", "-f", dev_node], capture_output=True)
        time.sleep(1)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        update_progress(10, "1/5: Creating GPT partition table...")
        subprocess.run(["parted", "-s", dev_node, "mklabel", "gpt"], check=True)
        subprocess.run(["parted", "-s", dev_node, "mkpart", "BOOT", "fat32", "1MiB", "51MiB"], check=True)
        subprocess.run(["parted", "-s", dev_node, "set", "1", "esp", "on"], check=True)
        subprocess.run(["parted", "-s", dev_node, "mkpart", "DATA", "ntfs", "51MiB", "100%"], check=True)

        subprocess.run(["partprobe", dev_node], capture_output=True)
        time.sleep(2)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        update_progress(15, "1/5: Formatting (FAT32 BOOT + NTFS DATA)...")
        subprocess.run(["mkfs.vfat", "-F32", "-n", "BOOT", p1], check=True)

        res_ntfs = subprocess.run(["mkfs.ntfs", "-f", "-L", custom_label, p2], capture_output=True)
        if res_ntfs.returncode != 0:
            raise Exception("NTFS format failed! Ensure 'ntfs-3g' is installed.")

        for path in [mount_boot, mount_data, mount_iso]:
            os.makedirs(path, exist_ok=True)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        update_progress(20, "2/5: Mounting targets...")
        subprocess.run(["mount", p1, mount_boot], check=True)
        subprocess.run(["mount", p2, mount_data], check=True)
        subprocess.run(["mount", "-o", "loop,ro", iso_path, mount_iso], check=True)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        update_progress(30, "3/5: Injecting EFI assets...")
        copy_and_patch_assets(get_asset_path("assets"), mount_boot)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        update_progress(40, "4/5: Transferring ISO image files...")
        copy_with_progress(mount_iso, mount_data)

        if cancel_requested: raise Exception("Operation cancelled by user.")

        update_progress(90, "5/5: Syncing buffers & unmounting...")
        subprocess.run(["sync"])
        force_unmount_leftovers(dev_node)

        update_progress(100, "Process Completed Successfully!")
        messagebox.showinfo("Success", "Bootable USB Drive is Ready!")

    except Exception as e:
        force_unmount_leftovers(dev_node)
        if "cancelled" in str(e).lower():
            update_progress(0, "Operation Cancelled!")
            messagebox.showwarning("Cancelled", "Operation was cancelled by user.")
        else:
            status_label.config(text="An error occurred!")
            messagebox.showerror("Operation Error", f"Details:\n{str(e)}")

    finally:
        btn_start.config(state="normal")
        btn_reset.config(state="normal")
        btn_refresh.config(state="normal")
        btn_cancel.config(state="disabled")

def start_process():
    global cancel_requested
    cancel_requested = False

    iso_path = os.path.abspath(iso_entry.get().strip().strip('"').strip("'"))
    selected_drive = drive_cb.get()

    if not os.path.exists(iso_path) or os.path.isdir(iso_path):
        messagebox.showerror("Error", f"Invalid ISO Path:\n{iso_path}")
        return

    if "No USB Drive Found!" in selected_drive:
        messagebox.showerror("Error", "Please select a valid USB target!")
        return

    if not messagebox.askyesno("WARNING!", f"Selected drive ({selected_drive}) will be ERASED!\nContinue?"):
        return

    btn_start.config(state="disabled")
    btn_reset.config(state="disabled")
    btn_refresh.config(state="disabled")
    btn_cancel.config(state="normal")

    threading.Thread(target=write_iso_worker, args=(selected_drive, iso_path), daemon=True).start()

drive_frame = tk.Frame(app)
drive_frame.pack(fill="x", padx=15, pady=(15, 2))

lbl_device = tk.Label(drive_frame, text=tr("target_device"), font=("Segoe UI", 9, "bold"))
lbl_device.pack(side="left")

lang_cb = ttk.Combobox(drive_frame, values=get_available_languages(), width=4, state="readonly")
lang_cb.set(current_lang)
lang_cb.pack(side="right", padx=(5, 0))
lang_cb.bind("<<ComboboxSelected>>", lambda e: change_language(lang_cb.get()))

btn_reset = ttk.Button(drive_frame, text=tr("clean_usb"), width=12, command=reset_usb_action)
btn_reset.pack(side="right", padx=(5, 0))

btn_refresh = ttk.Button(drive_frame, text=tr("refresh"), width=9, command=refresh_drives)
btn_refresh.pack(side="right")

drive_cb = ttk.Combobox(app, state="readonly")
drive_cb.pack(fill="x", padx=15)

lbl_boot = tk.Label(app, text=tr("boot_selection"), font=("Segoe UI", 9, "bold"))
lbl_boot.pack(anchor="w", padx=15, pady=(10, 2))

iso_frame = tk.Frame(app)
iso_frame.pack(fill="x", padx=15)

iso_entry = tk.Entry(app, state="readonly")
set_iso_text(tr("select_iso_placeholder"))
iso_entry.pack(in_=iso_frame, side="left", fill="x", expand=True, padx=(0, 5))

btn_split_frame = tk.Frame(iso_frame)
btn_split_frame.pack(side="right")

btn_iso_action = ttk.Button(btn_split_frame, text=tr("browse"), width=9, command=handle_iso_action)
btn_iso_action.pack(side="left")

btn_iso_arrow = ttk.Button(btn_split_frame, text="v", width=2, command=show_iso_menu)
btn_iso_arrow.pack(side="right")

iso_menu = tk.Menu(app, tearoff=0)
iso_menu.add_command(label=tr("menu_select"), command=lambda: set_iso_mode("select"))
iso_menu.add_command(label=tr("menu_download"), command=lambda: set_iso_mode("download"))

hash_frame = tk.Frame(app)
hash_frame.pack(fill="x", padx=15, pady=(10, 2))

lbl_hash = tk.Label(hash_frame, text=tr("sha_label"), font=("Segoe UI", 9, "bold"))
lbl_hash.pack(anchor="w")

hash_entry_frame = tk.Frame(hash_frame)
hash_entry_frame.pack(fill="x", pady=(2, 0))

hash_entry = tk.Entry(hash_entry_frame)
hash_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

btn_verify = ttk.Button(hash_entry_frame, text=tr("verify"), width=10, command=verify_sha_action)
btn_verify.pack(side="right")

lbl_partition = tk.Label(app, text=tr("partition_scheme"), font=("Segoe UI", 9, "bold"))
lbl_partition.pack(anchor="w", padx=15, pady=(10, 2))
partition_cb = ttk.Combobox(app, values=["GPT (UEFI)"], state="readonly")
partition_cb.current(0)
partition_cb.config(state="disabled")
partition_cb.pack(fill="x", padx=15)

lbl_fs = tk.Label(app, text=tr("target_fs"), font=("Segoe UI", 9, "bold"))
lbl_fs.pack(anchor="w", padx=15, pady=(10, 2))
fs_cb = ttk.Combobox(app, values=["NTFS (Dual-Partition UEFI Setup)"], state="readonly")
fs_cb.current(0)
fs_cb.pack(fill="x", padx=15)

lbl_label = tk.Label(app, text=tr("volume_label"), font=("Segoe UI", 9, "bold"))
lbl_label.pack(anchor="w", padx=15, pady=(10, 2))
label_entry = tk.Entry(app)
label_entry.insert(0, "LINUXFUS")
label_entry.pack(fill="x", padx=15)

status_label = tk.Label(app, text=tr("status_ready"), font=("Segoe UI", 8), fg="gray")
status_label.pack(anchor="w", padx=15, pady=(12, 2))

progress = ttk.Progressbar(app, mode="determinate")
progress.pack(fill="x", padx=15, pady=(2, 10))

btn_frame = tk.Frame(app)
btn_frame.pack(fill="x", padx=15, pady=5)

btn_start = ttk.Button(btn_frame, text=tr("start_write"), command=start_process)
btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)

btn_cancel = ttk.Button(btn_frame, text=tr("cancel"), command=cancel_process, state="disabled")
btn_cancel.pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)

dd_frame = tk.Frame(app)
dd_frame.pack(fill="x", padx=15, pady=(0, 10))
dd_var = tk.BooleanVar(value=False)
dd_check = ttk.Checkbutton(dd_frame, text=tr("dd_mode"), variable=dd_var)
dd_check.pack(side="left")

refresh_drives()
app.mainloop()
