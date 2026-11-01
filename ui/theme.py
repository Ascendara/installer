# theme.py
"""Shared design tokens, image rendering and Windows helpers for the installer UI."""
import os
import sys
import math
import logging
import tkinter.font as tkfont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Images are rendered at 2x and downscaled by CTkImage so they stay crisp on
# high-DPI displays.
SS = 2

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
DARK = {
    "bg": "#0E0C15",
    "surface": "#16131F",
    "surface_alt": "#211C2E",
    "surface_hover": "#2A2439",
    "border": "#2A2438",
    "text": "#F3F0FA",
    "text_muted": "#A39CB8",
    "text_subtle": "#6B6582",
    "accent": "#8A6BF0",
    "accent_hover": "#7A5BE0",
    "accent_soft": "#261F3D",
    "success": "#22C55E",
    "error": "#F05252",
    "close_hover": "#C42B1C",
    "log_info": "#C9C3DC",
    "log_warn": "#F5B544",
    "log_error": "#F87171",
    "log_time": "#6B6582",
}

LIGHT = {
    "bg": "#FFFFFF",
    "surface": "#F8F6FD",
    "surface_alt": "#EFEBF9",
    "surface_hover": "#E6E0F5",
    "border": "#E6E1F2",
    "text": "#17121F",
    "text_muted": "#5F5873",
    "text_subtle": "#9C95B0",
    "accent": "#7C5CEB",
    "accent_hover": "#6A4BD8",
    "accent_soft": "#EEE8FE",
    "success": "#16A34A",
    "error": "#DC2626",
    "close_hover": "#C42B1C",
    "log_info": "#3B354A",
    "log_warn": "#B45309",
    "log_error": "#DC2626",
    "log_time": "#9C95B0",
}


def is_windows_dark_mode():
    """Return True when Windows apps are set to use the dark theme."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        apps_use_light_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return apps_use_light_theme == 0
    except Exception as e:
        logging.warning(f"Could not detect Windows dark mode: {e}")
        return False


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
_families = None


def _available_families():
    global _families
    if _families is None:
        try:
            _families = set(tkfont.families())
        except Exception:
            _families = set()
    return _families


def ui_font():
    return "Segoe UI" if "Segoe UI" in _available_families() else "Arial"


def ui_font_semibold():
    fams = _available_families()
    if "Segoe UI Semibold" in fams:
        return "Segoe UI Semibold"
    return ui_font()


def icon_font():
    """Windows icon font (Fluent on Win11, MDL2 on Win10), or None."""
    fams = _available_families()
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if name in fams:
            return name
    return None


# Glyphs from Segoe Fluent Icons / Segoe MDL2 Assets, with plain-text fallbacks
GLYPHS = {
    "close": ("\uE8BB", "✕"),
    "minimize": ("\uE921", "—"),
    "logs": ("\uE8A5", "≡"),
    "retry": ("\uE72C", "↻"),
    "folder": ("\uE838", "▸"),
    "copy": ("\uE8C8", "⧉"),
    "clear": ("\uE74D", "✕"),
}


def glyph(name):
    icon, fallback = GLYPHS[name]
    return icon if icon_font() else fallback


def _pil_font(size, weight="regular"):
    """Load a Segoe UI TrueType font for PIL, falling back to PIL's default."""
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    files = {
        "regular": ["segoeui.ttf"],
        "semibold": ["seguisb.ttf", "segoeuib.ttf"],
        "bold": ["segoeuib.ttf", "seguisb.ttf"],
    }[weight]
    for f in files:
        try:
            return ImageFont.truetype(os.path.join(fonts_dir, f), size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# Image rendering
# --------------------------------------------------------------------------- #
def _hex(color, alpha=255):
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha)


def _vertical_gradient(w, h, top, bottom):
    top, bottom = _hex(top), _hex(bottom)
    strip = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        strip.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(4)))
    return strip.resize((w, h))


def _soft_ellipse(img, box, color, alpha, blur):
    """Composite a blurred ellipse. The layer is pre-filled with the same RGB at
    zero alpha so the blur doesn't drag black into the soft edge."""
    layer = Image.new("RGBA", img.size, _hex(color, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=_hex(color, alpha))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(blur)))


def render_hero(width, height, logo=None, version_text="", year=""):
    """Render the branded left-hand panel as a single image."""
    W, H = width * SS, height * SS
    # Soft white-lavender base, like the Ascendara app background
    img = _vertical_gradient(W, H, "#FDFBFF", "#F4EEFF")

    # Gentle pink / lavender washes for a subtle mesh-gradient look
    for cx, cy, r, color, a in (
        (0.10, 0.08, 0.70, "#E9DDFF", 230),
        (1.05, 0.55, 0.60, "#FBE3F3", 210),
        (0.05, 1.00, 0.75, "#E4DAFF", 220),
    ):
        R = r * W
        img = _soft_ellipse(img, (cx * W - R, cy * H - R, cx * W + R, cy * H + R), color, a, 70 * SS)

    # Faint dot grid that fades out towards the bottom
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(dots)
    step = 22 * SS
    for y in range(step // 2, H, step):
        a = int(40 * max(0.0, 1 - y / (H * 0.7)))
        if a <= 0:
            continue
        for x in range(step // 2, W, step):
            d.ellipse((x - SS, y - SS, x + SS, y + SS), fill=_hex("#B9A6EE", a))
    img = Image.alpha_composite(img, dots)

    # Logo: soft glow + white disc + image
    cx, cy = W // 2, int(H * 0.36)
    ring = 132 * SS
    g = ring * 0.55
    img = _soft_ellipse(img, (cx - g, cy - g, cx + g, cy + g), "#D9C8FF", 160, 30 * SS)

    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    gd.ellipse(
        (cx - ring // 2, cy - ring // 2, cx + ring // 2, cy + ring // 2),
        fill=(255, 255, 255, 170),
        outline=_hex("#E6DCFA", 255),
        width=SS,
    )
    img = Image.alpha_composite(img, glass)

    if logo is not None:
        size = 104 * SS
        lg = logo.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        alpha = Image.composite(lg.getchannel("A"), Image.new("L", (size, size), 0), mask)
        lg.putalpha(alpha)
        img.alpha_composite(lg, (cx - size // 2, cy - size // 2))
    else:
        f = _pil_font(56 * SS, "bold")
        ImageDraw.Draw(img).text((cx, cy), "A", font=f, fill=_hex("#6A3CB5"), anchor="mm")

    # Wordmark
    d = ImageDraw.Draw(img)
    d.text((cx, cy + ring // 2 + 44 * SS), "Ascendara", font=_pil_font(30 * SS, "bold"),
           fill=_hex("#2B1B4D"), anchor="mm")
    d.text((cx, cy + ring // 2 + 76 * SS), "Setup", font=_pil_font(14 * SS),
           fill=_hex("#8A73C4"), anchor="mm")

    # Footer
    footer = "  ·  ".join(p for p in (version_text, f"© {year} Ascendara" if year else "") if p)
    if footer:
        d.text((cx, H - 28 * SS), footer, font=_pil_font(11 * SS),
               fill=_hex("#A898CF"), anchor="mm")

    return img


def render_step_icon(state, colors, size=24, frame=0, frames=12):
    """Render a step indicator: pending, active (spinner frame), done or error."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = SS
    box = (pad, pad, S - pad - 1, S - pad - 1)
    w = 2 * SS

    if state == "pending":
        d.ellipse(box, outline=_hex(colors["border"]), width=w)
    elif state == "active":
        d.ellipse(box, fill=_hex(colors["accent_soft"]), outline=_hex(colors["accent_soft"]), width=w)
        start = (frame / frames) * 360
        d.arc(box, start=start, end=start + 100, fill=_hex(colors["accent"]), width=w)
        r = 3 * SS
        c = S / 2
        d.ellipse((c - r, c - r, c + r, c + r), fill=_hex(colors["accent"]))
    elif state == "done":
        d.ellipse(box, fill=_hex(colors["accent"]))
        pts = [(S * 0.30, S * 0.52), (S * 0.44, S * 0.66), (S * 0.71, S * 0.38)]
        d.line(pts, fill=(255, 255, 255, 255), width=int(2.2 * SS), joint="curve")
    elif state == "error":
        d.ellipse(box, fill=_hex(colors["error"]))
        a, b = S * 0.36, S * 0.64
        d.line([(a, a), (b, b)], fill=(255, 255, 255, 255), width=int(2.2 * SS))
        d.line([(a, b), (b, a)], fill=(255, 255, 255, 255), width=int(2.2 * SS))
    return img


# --------------------------------------------------------------------------- #
# Windows helpers (all best effort; no-ops elsewhere)
# --------------------------------------------------------------------------- #
def _hwnd(window):
    import ctypes
    return ctypes.windll.user32.GetParent(window.winfo_id())


def _dwm_set(window, attribute, value):
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        val = ctypes.c_int(value)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            _hwnd(window), attribute, ctypes.byref(val), ctypes.sizeof(val)
        )
        return res == 0
    except Exception as e:
        logging.debug(f"DwmSetWindowAttribute({attribute}) failed: {e}")
        return False


def round_corners(window):
    """Ask Windows 11 to round the window corners (DWMWA_WINDOW_CORNER_PREFERENCE)."""
    return _dwm_set(window, 33, 2)


def dark_title_bar(window, dark=True):
    """Use a dark native title bar (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    return _dwm_set(window, 20, 1 if dark else 0)


def make_app_window(window):
    """Give a frameless (overrideredirect) window a taskbar button so it can be minimized."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        GWL_EXSTYLE, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW = -20, 0x00040000, 0x00000080
        hwnd = _hwnd(window)
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        # Re-show so the shell picks up the new style
        window.withdraw()
        window.after(10, window.deiconify)
        return True
    except Exception as e:
        logging.debug(f"make_app_window failed: {e}")
        return False


def minimize(window):
    """Minimize a frameless window (Tk refuses to iconify override-redirect windows)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(_hwnd(window), 6)  # SW_MINIMIZE
            return
        except Exception as e:
            logging.debug(f"ShowWindow minimize failed: {e}")
    try:
        window.iconify()
    except Exception as e:
        logging.warning(f"Could not minimize window: {e}")


def resource_path(*parts):
    """Resolve a bundled resource both from source and from a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)
