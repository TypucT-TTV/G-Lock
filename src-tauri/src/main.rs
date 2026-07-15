// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(target_os = "windows")]
fn is_elevated() -> bool {
    use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
    use windows_sys::Win32::Security::{
        GetTokenInformation, TokenElevation, TOKEN_ELEVATION, TOKEN_QUERY,
    };
    use windows_sys::Win32::System::Threading::{GetCurrentProcess, OpenProcessToken};

    unsafe {
        let mut token: HANDLE = 0;
        if OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) != 0 {
            let mut elevation: TOKEN_ELEVATION = std::mem::zeroed();
            let mut size = std::mem::size_of::<TOKEN_ELEVATION>() as u32;
            let res = GetTokenInformation(
                token,
                TokenElevation,
                &mut elevation as *mut _ as *mut _,
                size,
                &mut size,
            );
            CloseHandle(token);
            if res != 0 {
                return elevation.TokenIsElevated != 0;
            }
        }
        false
    }
}

#[cfg(target_os = "windows")]
fn show_admin_warning() {
    use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};
    let title: Vec<u16> = "G-Lock - Ошибка запуска\0".encode_utf16().collect();
    let text: Vec<u16> = "Для работы фаервола необходимы права администратора.\nПожалуйста, запустите приложение от имени Администратора.\n\nFirewall requires administrator privileges.\nPlease run the application as Administrator.\0".encode_utf16().collect();
    unsafe {
        MessageBoxW(0, text.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR);
    }
}

fn main() {
    #[cfg(target_os = "windows")]
    {
        if !is_elevated() {
            show_admin_warning();
            std::process::exit(1);
        }
    }

    g_lock_tauri_lib::run();
}
