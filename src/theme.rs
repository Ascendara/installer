//! Design tokens, fonts and image rendering for the installer UI.

use std::sync::Arc;

use eframe::egui::{
    self, Color32, ColorImage, FontData, FontDefinitions, FontFamily, FontId, IconData, Stroke,
};
use image::{imageops::FilterType, RgbaImage};

/// The hero is rendered at 2x and downscaled so it stays crisp on high-DPI displays.
pub const SS: usize = 2;

const LOGO_PNG: &[u8] = include_bytes!("../readme/icon.png");
const ICON_ICO: &[u8] = include_bytes!("../ascendara.ico");

// --------------------------------------------------------------------------- //
// Palette
// --------------------------------------------------------------------------- //
#[derive(Clone, Copy)]
pub struct Palette {
    pub bg: Color32,
    pub surface: Color32,
    pub surface_alt: Color32,
    pub surface_hover: Color32,
    pub border: Color32,
    pub text: Color32,
    pub text_muted: Color32,
    pub text_subtle: Color32,
    pub accent: Color32,
    pub accent_hover: Color32,
    pub accent_soft: Color32,
    pub success: Color32,
    pub error: Color32,
    pub close_hover: Color32,
    pub log_info: Color32,
    pub log_warn: Color32,
    pub log_error: Color32,
    pub log_time: Color32,
}

pub const fn hex(v: u32) -> Color32 {
    Color32::from_rgb((v >> 16) as u8, (v >> 8) as u8, v as u8)
}

pub const DARK: Palette = Palette {
    bg: hex(0x0E0C15),
    surface: hex(0x16131F),
    surface_alt: hex(0x211C2E),
    surface_hover: hex(0x2A2439),
    border: hex(0x2A2438),
    text: hex(0xF3F0FA),
    text_muted: hex(0xA39CB8),
    text_subtle: hex(0x6B6582),
    accent: hex(0x8A6BF0),
    accent_hover: hex(0x7A5BE0),
    accent_soft: hex(0x261F3D),
    success: hex(0x22C55E),
    error: hex(0xF05252),
    close_hover: hex(0xC42B1C),
    log_info: hex(0xC9C3DC),
    log_warn: hex(0xF5B544),
    log_error: hex(0xF87171),
    log_time: hex(0x6B6582),
};

pub const LIGHT: Palette = Palette {
    bg: hex(0xFFFFFF),
    surface: hex(0xF8F6FD),
    surface_alt: hex(0xEFEBF9),
    surface_hover: hex(0xE6E0F5),
    border: hex(0xE6E1F2),
    text: hex(0x17121F),
    text_muted: hex(0x5F5873),
    text_subtle: hex(0x9C95B0),
    accent: hex(0x7C5CEB),
    accent_hover: hex(0x6A4BD8),
    accent_soft: hex(0xEEE8FE),
    success: hex(0x16A34A),
    error: hex(0xDC2626),
    close_hover: hex(0xC42B1C),
    log_info: hex(0x3B354A),
    log_warn: hex(0xB45309),
    log_error: hex(0xDC2626),
    log_time: hex(0x9C95B0),
};

pub fn apply_style(ctx: &egui::Context, c: &Palette, dark: bool) {
    ctx.set_theme(if dark { egui::Theme::Dark } else { egui::Theme::Light });
    let mut v = if dark { egui::Visuals::dark() } else { egui::Visuals::light() };
    v.panel_fill = c.bg;
    v.window_fill = c.bg;
    v.extreme_bg_color = c.surface;
    v.override_text_color = None;
    for w in [&mut v.widgets.inactive, &mut v.widgets.noninteractive] {
        w.bg_fill = c.surface_alt;
        w.weak_bg_fill = c.surface_alt;
    }
    for w in [&mut v.widgets.hovered, &mut v.widgets.active] {
        w.bg_fill = c.surface_hover;
        w.weak_bg_fill = c.surface_hover;
    }
    v.selection.bg_fill = c.accent.gamma_multiply(0.35);
    v.selection.stroke = Stroke::new(1.0_f32, c.text);
    ctx.set_visuals(v);
}

// --------------------------------------------------------------------------- //
// Fonts
// --------------------------------------------------------------------------- //
#[derive(Clone, Copy)]
pub enum Weight {
    Regular,
    Semibold,
    Bold,
}

pub fn font(size: f32, weight: Weight) -> FontId {
    let family = match weight {
        Weight::Regular => FontFamily::Proportional,
        Weight::Semibold => FontFamily::Name("semibold".into()),
        Weight::Bold => FontFamily::Name("bold".into()),
    };
    FontId::new(size, family)
}

/// Load Segoe UI (regular / semibold / bold) and Consolas from the Windows
/// fonts folder, falling back to egui's bundled fonts when missing.
pub fn install_fonts(ctx: &egui::Context) {
    let dir = std::path::PathBuf::from(std::env::var("WINDIR").unwrap_or_else(|_| r"C:\Windows".into()))
        .join("Fonts");
    let mut defs = FontDefinitions::default();
    let defaults = defs.families.get(&FontFamily::Proportional).cloned().unwrap_or_default();

    let mut load = |key: &str, files: &[&str]| -> Option<String> {
        let data = files.iter().find_map(|f| std::fs::read(dir.join(f)).ok())?;
        defs.font_data.insert(key.to_owned(), Arc::new(FontData::from_owned(data)));
        Some(key.to_owned())
    };
    let regular = load("segoe", &["segoeui.ttf"]);
    let semibold = load("segoe-semibold", &["seguisb.ttf", "segoeuib.ttf"]).or(regular.clone());
    let bold = load("segoe-bold", &["segoeuib.ttf", "seguisb.ttf"]).or(regular.clone());
    let mono = load("consolas", &["consola.ttf"]);

    let chain = |first: Option<String>| -> Vec<String> {
        first.into_iter().chain(defaults.iter().cloned()).collect()
    };
    defs.families.insert(FontFamily::Proportional, chain(regular));
    defs.families.insert(FontFamily::Name("semibold".into()), chain(semibold));
    defs.families.insert(FontFamily::Name("bold".into()), chain(bold));
    if let Some(m) = mono {
        defs.families.entry(FontFamily::Monospace).or_default().insert(0, m);
    }
    ctx.set_fonts(defs);
}

// --------------------------------------------------------------------------- //
// Images
// --------------------------------------------------------------------------- //
pub fn load_logo() -> Option<RgbaImage> {
    match image::load_from_memory(LOGO_PNG) {
        Ok(img) => Some(img.to_rgba8()),
        Err(e) => {
            log::error!("Error loading logo: {e}");
            None
        }
    }
}

pub fn window_icon() -> IconData {
    let img = image::load_from_memory_with_format(ICON_ICO, image::ImageFormat::Ico)
        .or_else(|_| image::load_from_memory(LOGO_PNG))
        .map(|i| i.resize(256, 256, FilterType::Lanczos3).to_rgba8());
    match img {
        Ok(i) => IconData { width: i.width(), height: i.height(), rgba: i.into_raw() },
        Err(_) => IconData::default(),
    }
}

type Rgb = [f32; 3];

fn rgbf(v: u32) -> Rgb {
    let c = hex(v);
    [c.r() as f32 / 255.0, c.g() as f32 / 255.0, c.b() as f32 / 255.0]
}

fn erf(x: f32) -> f32 {
    // Abramowitz & Stegun 7.1.26
    let s = x.signum();
    let x = x.abs();
    let t = 1.0 / (1.0 + 0.327_591_1 * x);
    let y = 1.0
        - (((((1.061_405_4 * t - 1.453_152_1) * t) + 1.421_413_7) * t - 0.284_496_74) * t
            + 0.254_829_6)
            * t
            * (-x * x).exp();
    s * y
}

/// Opaque float canvas with simple "source over" compositing.
struct Canvas {
    px: Vec<Rgb>,
    w: usize,
    h: usize,
}

impl Canvas {
    #[inline]
    fn blend(&mut self, x: usize, y: usize, col: Rgb, a: f32) {
        let p = &mut self.px[y * self.w + x];
        for k in 0..3 {
            p[k] += (col[k] - p[k]) * a;
        }
    }

    fn bounds(&self, cx: f32, cy: f32, r: f32) -> (usize, usize, usize, usize) {
        let x0 = (cx - r).floor().max(0.0) as usize;
        let y0 = (cy - r).floor().max(0.0) as usize;
        let x1 = ((cx + r).ceil().max(0.0) as usize).min(self.w);
        let y1 = ((cy + r).ceil().max(0.0) as usize).min(self.h);
        (x0, y0, x1, y1)
    }

    /// A Gaussian-blurred filled circle, computed analytically.
    fn soft_circle(&mut self, cx: f32, cy: f32, r: f32, col: Rgb, a: f32, sigma: f32) {
        let (x0, y0, x1, y1) = self.bounds(cx, cy, r + 4.0 * sigma);
        let k = 1.0 / (sigma * std::f32::consts::SQRT_2);
        for y in y0..y1 {
            for x in x0..x1 {
                let d = ((x as f32 + 0.5 - cx).powi(2) + (y as f32 + 0.5 - cy).powi(2)).sqrt();
                let alpha = a * 0.5 * (1.0 + erf((r - d) * k));
                if alpha > 0.001 {
                    self.blend(x, y, col, alpha);
                }
            }
        }
    }

    /// An anti-aliased filled circle.
    fn disc(&mut self, cx: f32, cy: f32, r: f32, col: Rgb, a: f32) {
        let (x0, y0, x1, y1) = self.bounds(cx, cy, r + 1.0);
        for y in y0..y1 {
            for x in x0..x1 {
                let d = ((x as f32 + 0.5 - cx).powi(2) + (y as f32 + 0.5 - cy).powi(2)).sqrt();
                let cov = (r - d + 0.5).clamp(0.0, 1.0);
                if cov > 0.0 {
                    self.blend(x, y, col, a * cov);
                }
            }
        }
    }

    /// An anti-aliased ring between radii `r - width` and `r`.
    fn ring(&mut self, cx: f32, cy: f32, r: f32, width: f32, col: Rgb, a: f32) {
        let (x0, y0, x1, y1) = self.bounds(cx, cy, r + 1.0);
        for y in y0..y1 {
            for x in x0..x1 {
                let d = ((x as f32 + 0.5 - cx).powi(2) + (y as f32 + 0.5 - cy).powi(2)).sqrt();
                let cov = (r - d + 0.5).clamp(0.0, 1.0) - (r - width - d + 0.5).clamp(0.0, 1.0);
                if cov > 0.0 {
                    self.blend(x, y, col, a * cov);
                }
            }
        }
    }

    fn into_image(self) -> ColorImage {
        let mut bytes = Vec::with_capacity(self.w * self.h * 4);
        for p in &self.px {
            for k in 0..3 {
                bytes.push((p[k].clamp(0.0, 1.0) * 255.0 + 0.5) as u8);
            }
            bytes.push(255);
        }
        ColorImage::from_rgba_unmultiplied([self.w, self.h], &bytes)
    }
}

/// Geometry of the hero (in 1x points), shared with the text drawn on top.
pub struct HeroLayout {
    pub logo_center_y: f32,
    pub ring: f32,
}

pub fn hero_layout(height: f32) -> HeroLayout {
    let h = height * SS as f32;
    HeroLayout { logo_center_y: (h * 0.36).floor() / SS as f32, ring: 132.0 }
}

/// Render the branded left-hand panel background (text is drawn on top by egui).
pub fn render_hero(width: usize, height: usize, logo: Option<&RgbaImage>) -> ColorImage {
    let (w, h) = (width * SS, height * SS);
    let (wf, hf, s) = (w as f32, h as f32, SS as f32);

    // Soft white-lavender base, like the Ascendara app background
    let (top, bottom) = (rgbf(0xFDFBFF), rgbf(0xF4EEFF));
    let mut px = Vec::with_capacity(w * h);
    for y in 0..h {
        let t = y as f32 / (h - 1).max(1) as f32;
        let c = [0, 1, 2].map(|k| top[k] + (bottom[k] - top[k]) * t);
        px.extend(std::iter::repeat(c).take(w));
    }
    let mut cv = Canvas { px, w, h };

    // Gentle pink / lavender washes for a subtle mesh-gradient look
    for (cx, cy, r, col, a) in [
        (0.10, 0.08, 0.70, 0xE9DDFF, 230.0),
        (1.05, 0.55, 0.60, 0xFBE3F3, 210.0),
        (0.05, 1.00, 0.75, 0xE4DAFF, 220.0),
    ] {
        cv.soft_circle(cx * wf, cy * hf, r * wf, rgbf(col), a / 255.0, 70.0 * s);
    }

    // Faint dot grid that fades out towards the bottom
    let step = 22 * SS;
    for y in (step / 2..h).step_by(step) {
        let a = (40.0 * (1.0 - y as f32 / (hf * 0.7)).max(0.0)).floor();
        if a <= 0.0 {
            continue;
        }
        for x in (step / 2..w).step_by(step) {
            cv.disc(x as f32 + 0.5, y as f32 + 0.5, s + 0.5, rgbf(0xB9A6EE), a / 255.0);
        }
    }

    // Logo: soft glow + white disc + image
    let (cx, cy) = ((w / 2) as f32, (hf * 0.36).floor());
    let ring = 132.0 * s;
    cv.soft_circle(cx, cy, ring * 0.55, rgbf(0xD9C8FF), 160.0 / 255.0, 30.0 * s);
    cv.disc(cx, cy, ring / 2.0 - s, [1.0; 3], 170.0 / 255.0);
    cv.ring(cx, cy, ring / 2.0, s, rgbf(0xE6DCFA), 1.0);

    if let Some(logo) = logo {
        let size = (104 * SS) as u32;
        let lg = resize_premultiplied(logo, size);
        let r = size as f32 / 2.0;
        let (ox, oy) = ((cx - r) as i64, (cy - r) as i64);
        for (x, y, p) in lg.enumerate_pixels() {
            let d = ((x as f32 + 0.5 - r).powi(2) + (y as f32 + 0.5 - r).powi(2)).sqrt();
            let mask = (r - d).clamp(0.0, 1.0);
            let a = p[3] as f32 / 255.0;
            if mask <= 0.0 || a <= 0.0 {
                continue;
            }
            let (px, py) = (ox + x as i64, oy + y as i64);
            if px < 0 || py < 0 || px as usize >= w || py as usize >= h {
                continue;
            }
            let col = [0, 1, 2].map(|k| (p[k] as f32 / 255.0) / a); // un-premultiply
            cv.blend(px as usize, py as usize, col, a * mask);
        }
    }

    cv.into_image()
}

/// Lanczos resize in premultiplied space so transparent edges don't go dark.
fn resize_premultiplied(img: &RgbaImage, size: u32) -> RgbaImage {
    let mut pm = img.clone();
    for p in pm.pixels_mut() {
        let a = p[3] as u16;
        for k in 0..3 {
            p[k] = ((p[k] as u16 * a + 127) / 255) as u8;
        }
    }
    image::imageops::resize(&pm, size, size, FilterType::Lanczos3)
}
