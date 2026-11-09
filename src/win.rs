//! Windows helpers. All best effort; no-ops on other platforms.

pub type Hwnd = isize;

#[cfg(windows)]
mod imp {
    use super::Hwnd;
    use std::ffi::c_void;
    use windows_sys::Win32::Graphics::Dwm::DwmSetWindowAttribute;
    use windows_sys::Win32::System::Registry::{RegGetValueW, HKEY_CURRENT_USER, RRF_RT_REG_DWORD};
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        FindWindowW, GetWindowLongPtrW, SetLayeredWindowAttributes, SetWindowLongPtrW,
        GWL_EXSTYLE, LWA_ALPHA, WS_EX_LAYERED,
    };

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn hwnd(h: Hwnd) -> *mut c_void {
        h as *mut c_void
    }

    /// True when Windows apps are set to use the dark theme.
    pub fn is_dark_mode() -> bool {
        let key = wide(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
        let value = wide("AppsUseLightTheme");
        let mut data: u32 = 1;
        let mut size = std::mem::size_of::<u32>() as u32;
        let res = unsafe {
            RegGetValueW(
                HKEY_CURRENT_USER,
                key.as_ptr(),
                value.as_ptr(),
                RRF_RT_REG_DWORD,
                std::ptr::null_mut(),
                &mut data as *mut u32 as *mut c_void,
                &mut size,
            )
        };
        if res != 0 {
            log::warn!("Could not detect Windows dark mode (error {res})");
            return false;
        }
        data == 0
    }

    fn dwm_set(h: Hwnd, attribute: u32, value: i32) -> bool {
        let res = unsafe {
            DwmSetWindowAttribute(
                hwnd(h),
                attribute,
                &value as *const i32 as *const c_void,
                std::mem::size_of::<i32>() as u32,
            )
        };
        res == 0
    }

    /// Ask Windows 11 to round the window corners (DWMWA_WINDOW_CORNER_PREFERENCE).
    pub fn round_corners(h: Hwnd) -> bool {
        dwm_set(h, 33, 2)
    }

    /// Use a dark/light native title bar (DWMWA_USE_IMMERSIVE_DARK_MODE).
    pub fn dark_title_bar(h: Hwnd, dark: bool) -> bool {
        dwm_set(h, 20, dark as i32)
    }

    /// Set whole-window opacity (0.0..=1.0) via a layered window.
    pub fn set_alpha(h: Hwnd, alpha: f32) {
        unsafe {
            let style = GetWindowLongPtrW(hwnd(h), GWL_EXSTYLE);
            if style & WS_EX_LAYERED as isize == 0 {
                SetWindowLongPtrW(hwnd(h), GWL_EXSTYLE, style | WS_EX_LAYERED as isize);
            }
            let a = (alpha.clamp(0.0, 1.0) * 255.0).round() as u8;
            SetLayeredWindowAttributes(hwnd(h), 0, a, LWA_ALPHA);
        }
    }

    pub fn find_window(title: &str) -> Option<Hwnd> {
        let t = wide(title);
        let h = unsafe { FindWindowW(std::ptr::null(), t.as_ptr()) };
        (!h.is_null()).then_some(h as Hwnd)
    }
}

#[cfg(not(windows))]
mod imp {
    use super::Hwnd;
    pub fn is_dark_mode() -> bool {
        false
    }
    pub fn round_corners(_: Hwnd) -> bool {
        false
    }
    pub fn dark_title_bar(_: Hwnd, _: bool) -> bool {
        false
    }
    pub fn set_alpha(_: Hwnd, _: f32) {}
    pub fn find_window(_: &str) -> Option<Hwnd> {
        None
    }
}

pub use imp::*;

/// Extract the Win32 HWND from anything exposing a raw window handle.
pub fn hwnd_of(w: &impl raw_window_handle::HasWindowHandle) -> Option<Hwnd> {
    match w.window_handle().ok()?.as_raw() {
        raw_window_handle::RawWindowHandle::Win32(h) => Some(h.hwnd.get()),
        _ => None,
    }
}
