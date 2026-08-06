#include <efi.h>
#include <efilib.h>

EFI_STATUS
EFIAPI
efi_main (EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable) {
    InitializeLib(ImageHandle, SystemTable);

    Print(L"[lfus-efi] Trigger initialized. Searching for target loader...\n");

    EFI_HANDLE TargetImageHandle;
    EFI_STATUS Status;

    EFI_DEVICE_PATH *FilePath = FileDevicePath(ImageHandle, L"\\EFI\\BOOT\\target_boot.efi");

    if (!FilePath) {
        Print(L"[lfus-efi] ERROR: Failed to construct device path.\n");
        return EFI_NOT_FOUND;
    }

    Status = uefi_call_wrapper(BS->LoadImage, 6, 
                               FALSE, 
                               ImageHandle, 
                               FilePath, 
                               NULL, 
                               0, 
                               &TargetImageHandle);

    if (EFI_ERROR(Status)) {
        Print(L"[lfus-efi] ERROR: Failed to load target image. Status: %r\n", Status);
        return Status;
    }

    Print(L"[lfus-efi] Target found and loaded. Handing over execution...\n");

    Status = uefi_call_wrapper(BS->StartImage, 3, 
                               TargetImageHandle, 
                               NULL, 
                               NULL);

    Print(L"[lfus-efi] WARNING: Target image returned or terminated unexpectedly.\n");

    return Status;
}
