# LinuxFus (v1.0)

LinuxFus is a simple Python script designed to help Linux users easily create bootable Windows USB drives without using complex terminal commands. It builds a dual-partition (FAT32 BOOT + NTFS DATA) GPT/UEFI layout, making Windows installation straightforward for everyone.

## Features

* **Dual-Partition UEFI Layout:** The BOOT partition (FAT32, ~50 MB) holds open-source `uefi-ntfs` bootloader files. The DATA partition (NTFS) stores the installation files, fully supporting `install.wim` or `install.esd` files larger than 4 GB.
* **Simple Graphical Interface (Tkinter GUI):** Clean layout with a progress bar, drive selector, and ISO picker.
* **Hardware Compatibility:** Creates a modern GPT partition table compatible with UEFI systems and Intel VMD / NVMe storage controllers.
* **Standalone AppImage:** Packed into a single executable file with all Python dependencies and boot assets included. No installation required.

## Prerequisites

Your system needs a few basic disk utilities (`ntfs-3g`, `parted`, `dosfstools`) to format FAT32 and NTFS partitions. Install them using the command for your Linux distribution:

* **Debian / Ubuntu / Linux Mint:** 
  ```bash
  sudo apt update && sudo apt install -y ntfs-3g parted dosfstools

  Arch Linux / Manjaro:

   sudo pacman -S --noconfirm ntfs-3g parted dosfstools

  Fedora:

  sudo dnf install -y ntfs-3g parted dosfstools

  How to Use
Go to the Releases section on the right side of this GitHub page and download the latest LinuxFus-x86_64.AppImage.

Open a terminal where the file is located and make it executable:

 chmod +x LinuxFus-x86_64.AppImage

 Run the AppImage with sudo privileges (required for raw disk partitioning and mounting):

  sudo ./LinuxFus-x86_64.AppImage

  Select your USB drive and Windows ISO file from the menu, then click START.

  How It Works
Unmounts any active partitions on the selected USB drive.

Uses parted to create a small FAT32 ESP partition for boot files and sets up the remaining space as an NTFS partition for Windows installation files.

Copies embedded open-source uefi-ntfs boot assets directly to the FAT32 partition.

Mounts your Windows ISO and transfers all contents to the NTFS partition.

Credits & References
This project uses open-source boot files and drivers developed by Pete Batard:

uefi-ntfs: Open-source UEFI bootloader that enables booting directly from NTFS partitions.

Author: Pete Batard (Akeo)

Source Code: https://github.com/pbatard/uefi-ntfs

Release Used: uefi-ntfs v2.8 (https://github.com/pbatard/uefi-ntfs/releases/tag/v2.8)

ntfs-3g (Akeo Release): Open-source NTFS driver binaries used for UEFI boot support.

Source & Release: https://github.com/pbatard/ntfs-3g/releases/tag/1.9

Rufus: Reliable USB creation utility for Windows.

Source Code: https://github.com/pbatard/rufus

License
Distributed under the MIT License. Free to use, modify, and share.
