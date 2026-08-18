#include <efi.h>
#include <efilib.h>

BOOLEAN IsSameDevicePath(EFI_DEVICE_PATH *Path1, EFI_DEVICE_PATH *Path2) {
    if (!Path1 || !Path2) return FALSE;
    
    CHAR16 *Str1 = DevicePathToStr(Path1);
    CHAR16 *Str2 = DevicePathToStr(Path2);
    
    BOOLEAN Match = FALSE;
    if (Str1 && Str2) {
        Match = (StrCmp(Str1, Str2) == 0);
    }
    
    if (Str1) uefi_call_wrapper(BS->FreePool, 1, Str1);
    if (Str2) uefi_call_wrapper(BS->FreePool, 1, Str2);
    
    return Match;
}

EFI_STATUS AutoScanAndBoot(
    EFI_HANDLE DeviceHandle, 
    EFI_FILE_HANDLE ParentDir, 
    CHAR16 *CurrentPath, 
    EFI_HANDLE ImageHandle, 
    EFI_DEVICE_PATH *SelfDevicePath
) {
    EFI_STATUS Status;
    EFI_FILE_INFO *FileInfo = NULL;
    UINTN BufferSize = 0;

    while (1) {
        BufferSize = 0;
        Status = uefi_call_wrapper(ParentDir->Read, 3, ParentDir, &BufferSize, NULL);
        if (Status != EFI_BUFFER_TOO_SMALL || BufferSize == 0) break;

        Status = uefi_call_wrapper(BS->AllocatePool, 3, EfiLoaderData, BufferSize, (VOID**)&FileInfo);
        if (EFI_ERROR(Status)) {
            uefi_call_wrapper(BS->Stall, 1, 5000000);
            break;
        }

        Status = uefi_call_wrapper(ParentDir->Read, 3, ParentDir, &BufferSize, FileInfo);
        if (EFI_ERROR(Status) || BufferSize == 0) {
            if (EFI_ERROR(Status)) {
                uefi_call_wrapper(BS->Stall, 1, 5000000);
            }
            uefi_call_wrapper(BS->FreePool, 1, FileInfo);
            break;
        }

        if (StrCmp(FileInfo->FileName, L".") == 0 || StrCmp(FileInfo->FileName, L"..") == 0) {
            uefi_call_wrapper(BS->FreePool, 1, FileInfo);
            continue;
        }

        UINTN PathLen = StrLen(CurrentPath) + StrLen(FileInfo->FileName) + 2;
        CHAR16 *FullPath = NULL;
        Status = uefi_call_wrapper(BS->AllocatePool, 3, EfiLoaderData, PathLen * sizeof(CHAR16), (VOID**)&FullPath);
        if (EFI_ERROR(Status)) {
            uefi_call_wrapper(BS->Stall, 1, 5000000);
            uefi_call_wrapper(BS->FreePool, 1, FileInfo);
            continue;
        }

        StrCpy(FullPath, CurrentPath);
        if (FullPath[StrLen(FullPath) - 1] != L'\\') {
            StrCat(FullPath, L"\\");
        }
        StrCat(FullPath, FileInfo->FileName);

        EFI_FILE_HANDLE ChildHandle = NULL;
        Status = uefi_call_wrapper(ParentDir->Open, 5, ParentDir, &ChildHandle, FileInfo->FileName, EFI_FILE_MODE_READ, 0);

        if (!EFI_ERROR(Status)) {
            if (FileInfo->Attribute & EFI_FILE_DIRECTORY) {
                Status = AutoScanAndBoot(DeviceHandle, ChildHandle, FullPath, ImageHandle, SelfDevicePath);
                uefi_call_wrapper(ParentDir->Close, 1, ChildHandle);
                
                if (Status == EFI_SUCCESS) {
                    uefi_call_wrapper(BS->FreePool, 1, FullPath);
                    uefi_call_wrapper(BS->FreePool, 1, FileInfo);
                    return EFI_SUCCESS;
                }
            } else {
                if (StriCmp(FileInfo->FileName, L"bootx64.efi") == 0) {
                    EFI_DEVICE_PATH *CandidatePath = FileDevicePath(DeviceHandle, FullPath);

                    if (CandidatePath && !IsSameDevicePath(SelfDevicePath, CandidatePath)) {
                        EFI_HANDLE TargetHandle = NULL;
                        Status = uefi_call_wrapper(BS->LoadImage, 6, FALSE, ImageHandle, CandidatePath, NULL, 0, &TargetHandle);
                        
                        if (!EFI_ERROR(Status)) {
                            uefi_call_wrapper(ParentDir->Close, 1, ChildHandle);
                            uefi_call_wrapper(BS->FreePool, 1, FullPath);
                            uefi_call_wrapper(BS->FreePool, 1, FileInfo);
                            
                            uefi_call_wrapper(BS->StartImage, 3, TargetHandle, NULL, NULL);
                            uefi_call_wrapper(BS->Exit, 4, ImageHandle, EFI_SUCCESS, 0, NULL);
                        } else {
                            uefi_call_wrapper(BS->Stall, 1, 5000000);
                        }
                    }
                }
                uefi_call_wrapper(ParentDir->Close, 1, ChildHandle);
            }
        }
        
        uefi_call_wrapper(BS->FreePool, 1, FullPath);
        uefi_call_wrapper(BS->FreePool, 1, FileInfo);
    }
    return EFI_NOT_FOUND;
}

EFI_STATUS
EFIAPI
efi_main (EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable) {
    EFI_STATUS Status;
    UINTN HandleCount = 0;
    EFI_HANDLE *HandleBuffer = NULL;
    EFI_LOADED_IMAGE *LoadedImage = NULL;
    EFI_DEVICE_PATH *SelfDevicePath = NULL;

    InitializeLib(ImageHandle, SystemTable);

    Status = uefi_call_wrapper(BS->HandleProtocol, 3, ImageHandle, &gEfiLoadedImageProtocolGuid, (VOID**)&LoadedImage);
    if (!EFI_ERROR(Status)) {
        EFI_DEVICE_PATH *DevicePath = DevicePathFromHandle(LoadedImage->DeviceHandle);
        SelfDevicePath = AppendDevicePath(DevicePath, LoadedImage->FilePath);
    }

    Status = uefi_call_wrapper(BS->LocateHandleBuffer, 5, ByProtocol, &gEfiSimpleFileSystemProtocolGuid, NULL, &HandleCount, &HandleBuffer);
    if (EFI_ERROR(Status)) {
        uefi_call_wrapper(BS->Stall, 1, 5000000);
        return Status;
    }

    for (UINTN i = 0; i < HandleCount; i++) {
        EFI_FILE_IO_INTERFACE *FileSystem = NULL;
        EFI_FILE_HANDLE RootDir = NULL;

        Status = uefi_call_wrapper(BS->HandleProtocol, 3, HandleBuffer[i], &gEfiSimpleFileSystemProtocolGuid, (VOID**)&FileSystem);
        if (EFI_ERROR(Status)) continue;

        Status = uefi_call_wrapper(FileSystem->OpenVolume, 2, FileSystem, &RootDir);
        if (EFI_ERROR(Status)) continue;

        Status = AutoScanAndBoot(HandleBuffer[i], RootDir, L"\\", ImageHandle, SelfDevicePath);
        uefi_call_wrapper(RootDir->Close, 1, RootDir);

        if (Status == EFI_SUCCESS) break;
    }

    if (HandleBuffer) uefi_call_wrapper(BS->FreePool, 1, HandleBuffer);
    
    uefi_call_wrapper(BS->Stall, 1, 5000000);
    return EFI_NOT_FOUND;
}
