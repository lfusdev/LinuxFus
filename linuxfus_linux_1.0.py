#!/usr/bin/env python3
import subprocess
import json
import platform
import os
import threading
import shutil
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

cancel_requested = False


def get_asset_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def patch_efi_data(binary_data, old_name="rufus", new_name="lfus_"):
    if len(old_name) != len(new_name):
        raise ValueError("Old and new folder names must be of equal length! (5 characters)")

    old_ascii = old_name.encode('ascii')
    new_ascii = new_name.encode('ascii')
    old_utf16 = old_name.encode('utf-16le')
    new_utf16 = new_name.encode('utf-16le')

    return binary_data.replace(old_ascii, new_ascii).replace(old_utf16, new_utf16)


def is_root():
    return os.geteuid() == 0

if not is_root():
    print("[ERROR] This script requires root privileges because it performs disk operations!")
    print("Please run from the terminal as: 'sudo python3 linuxfus_linux.py'")

app = tk.Tk()
app.title("LinuxFus v1.0 (Linux)")
app.geometry("430x620")
app.resizable(False, False)


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
    except Exception as e:
        print("Linux scanning error:", e)

    if not drives:
        drives = ["No USB Drive Found!"]
    
    return drives

def refresh_drives():
    usb_list = get_usb_drives()
    drive_cb['values'] = usb_list
    drive_cb.current(0)

def select_iso():
    file_path = filedialog.askopenfilename(
        title="Select ISO File",
        filetypes=[("ISO Files", "*.iso"), ("All Files", "*.*")]
    )
    if file_path:
        iso_entry.delete(0, tk.END)
        iso_entry.insert(0, file_path)
        
        iso_filename = os.path.splitext(os.path.basename(file_path))[0]
        custom_label = iso_filename[:11].replace(" ", "_").upper()
        label_entry.delete(0, tk.END)
        label_entry.insert(0, custom_label if custom_label else "LINUXFUS")


def cancel_process():
    global cancel_requested
    if messagebox.askyesno("Cancel", "Are you sure you want to cancel the writing process?"):
        cancel_requested = True
        status_label.config(text="Status: Cancelling...")
        btn_cancel.config(state="disabled")

def start_process():
    global cancel_requested
    cancel_requested = False

    if not is_root():
        messagebox.showerror("Permission Error", "Program was not run with Root (sudo) privileges!\nPlease open with 'sudo' from the terminal.")
        return

    iso_path = iso_entry.get().strip().strip('"').strip("'")
    iso_path = os.path.abspath(iso_path)
    selected_drive = drive_cb.get()

    if not os.path.exists(iso_path) or os.path.isdir(iso_path):
        messagebox.showerror("Error", f"ISO File Not Found!\n\nEntered Path:\n{iso_path}")
        return

    if "No USB Drive Found!" in selected_drive:
        messagebox.showerror("Error", "Please select a valid USB drive!")
        return

    confirm = messagebox.askyesno(
        "WARNING!",
        f"The selected drive ({selected_drive}) will be COMPLETELY FORMATTED!\nEverything on it will be erased. Do you want to continue?"
    )
    if not confirm:
        return

    btn_start.config(state="disabled")
    btn_refresh.config(state="disabled")
    btn_cancel.config(state="normal")
    
    threading.Thread(target=write_iso_worker, args=(selected_drive, iso_path), daemon=True).start()

def update_progress(val, text=""):
    progress['value'] = val
    if text:
        status_label.config(text=text)
    app.update_idletasks()

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

    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dest_dir = os.path.join(dst, rel_path) if rel_path != "." else dst
        os.makedirs(dest_dir, exist_ok=True)

        for f in files:
            if cancel_requested:
                raise Exception("Operation cancelled by the user.")

            src_file = os.path.join(root, f)
            dst_file = os.path.join(dest_dir, f)

            with open(src_file, 'rb') as fsrc, open(dst_file, 'wb') as fdst:
                while True:
                    if cancel_requested:
                        raise Exception("Operation cancelled by the user.")
                    buf = fsrc.read(1024 * 1024)  # 1MB chunks
                    if not buf:
                        break
                    fdst.write(buf)
                    copied_bytes += len(buf)

                    pct = int((copied_bytes / total_bytes) * 100) if total_bytes > 0 else 0
                    mapped_progress = 40 + int(pct * 0.5)
                    update_progress(mapped_progress, f"4/5: Copying Files... %{pct}")

def copy_and_patch_assets(assets_dir, target_drive):
    global cancel_requested
    if os.path.exists(assets_dir):
        for root, dirs, files in os.walk(assets_dir):
            rel_path = os.path.relpath(root, assets_dir)
            dest_dir = os.path.join(target_drive, rel_path) if rel_path != "." else target_drive
            os.makedirs(dest_dir, exist_ok=True)

            for f in files:
                if cancel_requested: raise Exception("Operation cancelled by the user.")
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
        raise Exception("Critical Error: 'assets' folder not found!\nPlease place the 'assets' folder next to the script.")

def write_iso_worker(selected_drive, iso_path):
    global cancel_requested
    
    mount_boot = "/tmp/lfus_boot"
    mount_data = "/tmp/lfus_data"
    mount_iso = "/tmp/lfus_iso"

    try:
        custom_label = label_entry.get().strip().replace(" ", "_")
        if not custom_label:
            custom_label = "LINUXFUS"
        custom_label = custom_label[:11]

        dev_node = selected_drive.split()[0]  # e.g., /dev/sdb

        
        if "nvme" in dev_node or "mmcblk" in dev_node:
            p1 = f"{dev_node}p1"
            p2 = f"{dev_node}p2"
        else:
            p1 = f"{dev_node}1"
            p2 = f"{dev_node}2"

        
        update_progress(5, "1/5: Unmounting drive connections...")
        subprocess.run(["umount", p1], capture_output=True)
        subprocess.run(["umount", p2], capture_output=True)
        subprocess.run(["umount", dev_node], capture_output=True)

        
        update_progress(10, f"1/5: Creating GPT partition table...")
        subprocess.run(["parted", "-s", dev_node, "mklabel", "gpt"], check=True)
        subprocess.run(["parted", "-s", dev_node, "mkpart", "BOOT", "fat32", "1MiB", "51MiB"], check=True)
        subprocess.run(["parted", "-s", dev_node, "set", "1", "esp", "on"], check=True)
        subprocess.run(["parted", "-s", dev_node, "mkpart", "DATA", "ntfs", "51MiB", "100%"], check=True)

        
        subprocess.run(["partprobe", dev_node], capture_output=True)
        time.sleep(2)

        update_progress(15, "1/5: Formatting (FAT32 BOOT + NTFS DATA)...")
        
        
        subprocess.run(["mkfs.vfat", "-F32", "-n", "BOOT", p1], check=True)
        
        
        res_ntfs = subprocess.run(["mkfs.ntfs", "-f", "-L", custom_label, p2], capture_output=True)
        if res_ntfs.returncode != 0:
            raise Exception("NTFS formatting failed! Please ensure 'ntfs-3g' is installed on your system.")

        
        for path in [mount_boot, mount_data, mount_iso]:
            os.makedirs(path, exist_ok=True)

        update_progress(20, "2/5: Mounting drives and ISO...")
        subprocess.run(["mount", p1, mount_boot], check=True)
        subprocess.run(["mount", p2, mount_data], check=True)
        subprocess.run(["mount", "-o", "loop,ro", iso_path, mount_iso], check=True)

        if cancel_requested: raise Exception("Operation cancelled by the user.")

        
        update_progress(30, "3/5: Injecting and patching boot files...")
        copy_and_patch_assets(get_asset_path("assets"), mount_boot)

        
        update_progress(40, "4/5: Transferring ISO contents...")
        copy_with_progress(mount_iso, mount_data)

        
        update_progress(90, "5/5: Cleaning up and unmounting...")
        subprocess.run(["umount", mount_boot], capture_output=True)
        subprocess.run(["umount", mount_data], capture_output=True)
        subprocess.run(["umount", mount_iso], capture_output=True)

        update_progress(100, "Process Completed Successfully! 🎉")
        messagebox.showinfo("Success", "Bootable USB is Ready!")

    except Exception as e:
        subprocess.run(["umount", mount_boot], capture_output=True)
        subprocess.run(["umount", mount_data], capture_output=True)
        subprocess.run(["umount", mount_iso], capture_output=True)

        if "cancelled" in str(e).lower() or "iptal" in str(e):
            update_progress(0, "Cancelled!")
            messagebox.showwarning("Cancelled", "Operation cancelled by the user.")
        else:
            status_label.config(text="An error occurred!")
            messagebox.showerror("Operation Error", f"Error details:\n{str(e)}")

    finally:
        btn_start.config(state="normal")
        btn_refresh.config(state="normal")
        btn_cancel.config(state="disabled")


drive_frame = tk.Frame(app)
drive_frame.pack(fill="x", padx=15, pady=(15, 2))

tk.Label(drive_frame, text="Device / Drive:", font=("Segoe UI", 9, "bold")).pack(side="left")
btn_refresh = ttk.Button(drive_frame, text="🔄 Refresh", width=8, command=refresh_drives)
btn_refresh.pack(side="right")

drive_cb = ttk.Combobox(app, state="readonly")
drive_cb.pack(fill="x", padx=15)

tk.Label(app, text="Boot Selection (ISO):", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(10, 2))
iso_frame = tk.Frame(app)
iso_frame.pack(fill="x", padx=15)

iso_entry = tk.Entry(iso_frame)
iso_entry.insert(0, "Please select an ISO file...")
iso_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

btn_browse = ttk.Button(iso_frame, text="SELECT", command=select_iso)
btn_browse.pack(side="right")

tk.Label(app, text="Partition Scheme:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(10, 2))
partition_cb = ttk.Combobox(app, values=["GPT (UEFI)", "MBR (Legacy/CSM)"], state="readonly")
partition_cb.current(0)
partition_cb.pack(fill="x", padx=15)

tk.Label(app, text="File System:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(10, 2))
fs_cb = ttk.Combobox(app, values=["NTFS (Dual-Partition UEFI)"], state="readonly")
fs_cb.current(0)
fs_cb.pack(fill="x", padx=15)

tk.Label(app, text="USB Drive Name (Volume Label):", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(10, 2))
label_entry = tk.Entry(app)
label_entry.insert(0, "LINUXFUS")
label_entry.pack(fill="x", padx=15)

status_label = tk.Label(app, text="Status: Ready", font=("Segoe UI", 8), fg="gray")
status_label.pack(anchor="w", padx=15, pady=(12, 2))

progress = ttk.Progressbar(app, mode="determinate")
progress.pack(fill="x", padx=15, pady=(2, 10))

btn_frame = tk.Frame(app)
btn_frame.pack(fill="x", padx=15, pady=5)

btn_start = ttk.Button(btn_frame, text="START", command=start_process)
btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)

btn_cancel = ttk.Button(btn_frame, text="CANCEL", command=cancel_process, state="disabled")
btn_cancel.pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)

refresh_drives()

app.mainloop()