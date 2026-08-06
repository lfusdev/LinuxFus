# LinuxFus (v1.2.1)

LinuxFus is a lightweight graphical USB writing utility built with Python (Tkinter) and custom C boot logic. It helps Linux users create bootable USB drives without memorizing terminal commands, using a simple dual-partition layout (FAT32 BOOT + DATA) that works smoothly across various Linux distributions and Windows ISOs.

---

## What's New in v1.2.1

* **Custom C EFI Loader:** Replaced third-party external UEFI drivers with an in-house C-based boot loader (`bootx64.efi`).
* **Clean Handover:** The custom loader simply finds the target ISO's boot files, hands over execution, and unloads itself from memory immediately.
* **Broader ISO Support:** Partition structure tuned to work with standard OS installation images (Arch Linux, Ubuntu, Debian, Fedora, Windows, etc.).
* **GUI Improvements:** Minor UI polish and progress updates in the Tkinter interface.

---

## Features

* **Dual-Partition Layout:** Keeps boot assets in a small FAT32 partition (~50 MB) while the main DATA partition handles large installation files (>4 GB).
* **Simple GUI:** Choose your USB drive, pick an ISO, and hit start.
* **Hardware Ready:** Prepares GPT partition tables compatible with modern UEFI systems and NVMe drives.
* **AppImage Format:** Runs as a single portable file with bundled Python dependencies.

---

## Prerequisites

Make sure your system has basic disk utilities installed:

### Debian / Ubuntu / Linux Mint:
`sudo apt update && sudo apt install -y ntfs-3g parted dosfstools`

### Arch Linux / Manjaro:
`sudo pacman -S ntfs-3g parted dosfstools`

### Fedora:
`sudo dnf install -y ntfs-3g parted dosfstools`

---

## How to Use

1. Download the latest `LinuxFus-v1.2.1-x86_64.AppImage` from the **Releases** section.
2. Make it executable:
   `chmod +x LinuxFus-v1.2.1-x86_64.AppImage`
3. Run with root privileges (needed for disk formatting and mounting):
   `sudo ./LinuxFus-v1.2.1-x86_64.AppImage`
4. Select your USB drive and ISO file, then click **START**.

---

## How It Works

1. Unmounts the target USB drive safely.
2. Prepares a FAT32 ESP partition alongside a main data partition using `parted`.
3. Copies the embedded C boot loader (`/EFI/BOOT/BOOTX64.EFI`) to the boot partition.
4. Mounts the source ISO and copies installation files to the target partition.
5. On boot, the loader executes the target OS's native boot file and steps out of the way.

---

## License

Distributed under the **MIT License**.
