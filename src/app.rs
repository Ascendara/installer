//! Main installer window.

use std::f32::consts::TAU;
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;
use std::time::{Duration, Instant};

use eframe::egui::{
    self, pos2, vec2, Align2, Color32, CornerRadius, CursorIcon, FontId, Id, Painter, PointerButton,
    Pos2, Rect, Sense, Shape, Stroke, StrokeKind, TextureHandle, TextureOptions, Ui,
    ViewportCommand,
};

use crate::installer::{self, Msg, Reporter};
use crate::log_window::LogWindow;
use crate::theme::{self, font, Palette, Weight};
use crate::{win, VERSION};

pub const WIDTH: f32 = 860.0;
pub const HEIGHT: f32 = 540.0;
const HERO_WIDTH: f32 = 300.0;
const PAD_X: f32 = 44.0;
const CARD_HEIGHT: f32 = 102.0;
const FOOTER_HEIGHT: f32 = 64.0;
/// One spinner revolution (12 frames x 70 ms in the original).
const SPINNER_PERIOD: f32 = 0.84;

const STEPS: [(&str, &str); 3] = [
    ("Download", "Fetching the latest release"),
    ("Install", "Running the Ascendara setup"),
    ("Launch", "Opening Ascendara"),
];

#[derive(Clone, Copy, PartialEq, Eq)]
enum Step {
    Pending,
    Active,
    Done,
    Error,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Subtitle {
    Installing,
    Success,
    Failed,
}

pub struct InstallerApp {
    c: Palette,
    dark: bool,
    hwnd: Option<win::Hwnd>,
    hero: TextureHandle,
    icon: Arc<egui::IconData>,

    tx: Sender<(u64, Msg)>,
    rx: Receiver<(u64, Msg)>,
    generation: u64,
    version_rx: Receiver<String>,
    app_version: Option<String>,

    // Visible state
    steps: [Step; 3],
    eyebrow_step: usize,
    heading: String,
    subtitle: Subtitle,
    status: String,
    detail: String,
    percentage: String,
    percentage_color: Color32,
    bar_color: Color32,
    show_retry: bool,
    secondary_label: &'static str,

    // Progress animation
    target: f32,
    shown: f32,
    animating: bool,
    indeterminate: bool,
    indeterminate_t0: Instant,
    spinner_t0: Instant,
    last_status: String,

    // Lifecycle
    alpha: f32,
    fade_in_done: bool,
    closing: bool,
    close_sent: bool,
    launch_done_at: Option<Instant>,
    auto_close_at: Option<Instant>,
    logs: Option<LogWindow>,
}

impl InstallerApp {
    pub fn new(
        cc: &eframe::CreationContext<'_>,
        icon: Arc<egui::IconData>,
        logo: Option<image::RgbaImage>,
    ) -> Self {
        log::info!("Initializing main window");
        let dark = win::is_dark_mode();
        log::info!("Windows dark mode detected: {}", if dark { "True" } else { "False" });
        let c = if dark { theme::DARK } else { theme::LIGHT };

        let ctx = &cc.egui_ctx;
        theme::install_fonts(ctx);
        theme::apply_style(ctx, &c, dark);

        let hero = ctx.load_texture(
            "hero",
            theme::render_hero(HERO_WIDTH as usize, HEIGHT as usize, logo.as_ref()),
            TextureOptions::LINEAR,
        );

        // Start transparent (fade in) with rounded corners
        let hwnd = win::hwnd_of(cc).or_else(|| win::find_window("Ascendara Installer"));
        if let Some(h) = hwnd {
            win::set_alpha(h, 0.0);
            win::round_corners(h);
        }

        log::info!("Installer Version {VERSION}");

        // Fetch the app version for the subtitle, off the UI thread
        let (version_tx, version_rx) = mpsc::channel();
        let repaint = ctx.clone();
        let _ = std::thread::Builder::new().name("version".into()).spawn(move || {
            match installer::fetch_display_version() {
                Ok(Some(v)) => {
                    let _ = version_tx.send(v);
                    repaint.request_repaint();
                }
                Ok(None) => {}
                Err(e) => log::warn!("Could not fetch app version: {e}"),
            }
        });

        let (tx, rx) = mpsc::channel();
        let now = Instant::now();
        Self {
            c,
            dark,
            hwnd,
            hero,
            icon,
            tx,
            rx,
            generation: 0,
            version_rx,
            app_version: None,
            steps: [Step::Pending; 3],
            eyebrow_step: 0,
            heading: "Getting things ready".into(),
            subtitle: Subtitle::Installing,
            status: "Preparing…".into(),
            detail: String::new(),
            percentage: String::new(),
            percentage_color: c.text_muted,
            bar_color: c.accent,
            show_retry: false,
            secondary_label: "Cancel",
            target: 0.0,
            shown: 0.0,
            animating: false,
            indeterminate: false,
            indeterminate_t0: now,
            spinner_t0: now,
            last_status: String::new(),
            alpha: 0.0,
            fade_in_done: false,
            closing: false,
            close_sent: false,
            launch_done_at: None,
            auto_close_at: None,
            logs: None,
        }
    }

    // ------------------------------------------------------------------ //
    // Helpers
    // ------------------------------------------------------------------ //
    fn subtitle_text(&self) -> String {
        match self.subtitle {
            Subtitle::Installing => {
                let ver = match &self.app_version {
                    Some(v) => format!("version {v}"),
                    None => "the latest version".into(),
                };
                format!(
                    "Installing {ver} of Ascendara on your computer. \
                     It will launch automatically once setup is complete."
                )
            }
            Subtitle::Success => "Ascendara was installed successfully and is launching now. \
                                  This window will close on its own."
                .into(),
            Subtitle::Failed => "Something went wrong while installing Ascendara. \
                                 Check your connection and try again, or open the logs for details."
                .into(),
        }
    }

    fn truncate(text: &str) -> String {
        const LIMIT: usize = 64;
        if text.chars().count() <= LIMIT {
            return text.to_owned();
        }
        let cut: String = text.chars().take(LIMIT - 1).collect();
        format!("{}…", cut.trim_end())
    }

    fn set_step(&mut self, i: usize, state: Step) {
        self.steps[i] = state;
        if let Some(active) = self.steps.iter().position(|s| matches!(s, Step::Active | Step::Error)) {
            self.eyebrow_step = active;
        }
    }

    fn set_indeterminate(&mut self, on: bool) {
        if on == self.indeterminate {
            return;
        }
        self.indeterminate = on;
        if on {
            self.indeterminate_t0 = Instant::now();
            self.percentage.clear();
        }
    }

    // ------------------------------------------------------------------ //
    // Installer events
    // ------------------------------------------------------------------ //
    fn drain_messages(&mut self) {
        while let Ok((generation, msg)) = self.rx.try_recv() {
            if generation != self.generation {
                continue;
            }
            match msg {
                Msg::Progress(p) => self.apply_progress(p),
                Msg::Status(s) => self.apply_status(s),
                Msg::Complete(ok) => self.apply_complete(ok),
            }
        }
        while let Ok(v) = self.version_rx.try_recv() {
            self.app_version = Some(v);
        }
    }

    fn apply_progress(&mut self, progress: Option<f32>) {
        let Some(value) = progress else {
            self.set_indeterminate(true);
            return;
        };
        let value = value.clamp(0.0, 1.0);
        self.set_indeterminate(false);
        if value < self.target - 0.5 {
            // A fresh download started (e.g. backup mirror)
            self.shown = 0.0;
        }
        self.target = value;
        self.animating = true;
    }

    fn apply_status(&mut self, text: String) {
        log::info!("Status update: {text}");
        let lower = text.to_lowercase();
        if lower.contains("running installer") {
            self.set_step(0, Step::Done);
            self.set_step(1, Step::Active);
            self.heading = "Installing Ascendara".into();
            self.status = "Running setup…".into();
            self.detail = "Follow any prompts from the Ascendara setup window".into();
        } else if lower.starts_with("downloading") {
            self.set_step(0, Step::Active);
            self.heading = "Downloading Ascendara".into();
            self.status = "Downloading…".into();
            self.detail = Self::truncate(&text);
        } else {
            self.detail = Self::truncate(&text);
        }
        self.last_status = text;
    }

    fn apply_complete(&mut self, success: bool) {
        let c = self.c;
        self.set_indeterminate(false);
        self.animating = false;
        if success {
            log::info!("Installation completed successfully");
            self.set_step(0, Step::Done);
            self.set_step(1, Step::Done);
            self.set_step(2, Step::Active);
            self.target = 1.0;
            self.shown = 1.0;
            self.bar_color = c.success;
            self.percentage = "100%".into();
            self.percentage_color = c.success;
            self.heading = "You're all set".into();
            self.subtitle = Subtitle::Success;
            self.status = "Installation complete".into();
            self.detail = "Launching Ascendara…".into();
            self.secondary_label = "Close";
            let now = Instant::now();
            self.launch_done_at = Some(now + Duration::from_millis(1200));
            self.auto_close_at = Some(now + Duration::from_millis(2200));
        } else {
            log::error!("Installation failed");
            let failed = self.steps.iter().position(|s| *s == Step::Active).unwrap_or(0);
            self.set_step(failed, Step::Error);
            self.bar_color = c.error;
            self.percentage.clear();
            self.percentage_color = c.text_muted;
            self.heading = "Installation failed".into();
            self.subtitle = Subtitle::Failed;
            self.status = "Couldn't finish setup".into();
            self.detail = Self::truncate(if self.last_status.is_empty() {
                "See logs for details"
            } else {
                &self.last_status
            });
            self.secondary_label = "Exit";
            self.show_retry = true;
        }
    }

    // ------------------------------------------------------------------ //
    // Installation control
    // ------------------------------------------------------------------ //
    fn start_installation(&mut self, ctx: &egui::Context) {
        let c = self.c;
        self.steps = [Step::Active, Step::Pending, Step::Pending];
        self.eyebrow_step = 0;
        self.heading = "Getting things ready".into();
        self.subtitle = Subtitle::Installing;
        self.status = "Preparing…".into();
        self.detail = "Connecting to Ascendara servers".into();
        self.percentage.clear();
        self.percentage_color = c.text_muted;
        self.bar_color = c.accent;
        self.target = 0.0;
        self.shown = 0.0;
        self.animating = false;
        self.show_retry = false;
        self.secondary_label = "Cancel";
        self.set_indeterminate(true);

        self.generation += 1;
        let rep = Reporter { tx: self.tx.clone(), generation: self.generation, ctx: ctx.clone() };
        match installer::spawn(rep) {
            Ok(()) => log::info!("Installation process started"),
            Err(e) => {
                log::error!("Failed to start installation: {e}");
                self.last_status = e.to_string();
                self.apply_complete(false);
            }
        }
    }

    fn retry(&mut self, ctx: &egui::Context) {
        log::info!("Retrying installation");
        self.set_indeterminate(false);
        self.start_installation(ctx);
    }

    fn show_logs(&mut self, ctx: &egui::Context) {
        log::info!("Opening log window...");
        match &mut self.logs {
            Some(lw) => lw.focus(),
            None => {
                // Centre it over the installer
                let main = ctx.input(|i| i.viewport().outer_rect);
                let pos = main.map(|r| {
                    let p = r.min + vec2((WIDTH - 820.0) / 2.0, (HEIGHT - 520.0) / 2.0);
                    pos2(p.x.max(0.0), p.y.max(0.0))
                });
                self.logs = Some(LogWindow::new(pos));
            }
        }
    }

    fn close(&mut self) {
        if self.closing {
            return;
        }
        self.closing = true;
        if self.logs.take().is_some() {
            log::info!("Log window closed");
        }
        self.launch_done_at = None;
        self.auto_close_at = None;
    }

    // ------------------------------------------------------------------ //
    // Per-frame animation
    // ------------------------------------------------------------------ //
    fn tick(&mut self, ctx: &egui::Context) {
        let dt = ctx.input(|i| i.stable_dt).clamp(0.0, 0.05);
        let now = Instant::now();

        if self.closing {
            self.alpha = (self.alpha - dt / 0.16).max(0.0);
            self.set_window_alpha();
            if self.alpha <= 0.0 && !self.close_sent {
                self.close_sent = true;
                ctx.send_viewport_cmd(ViewportCommand::Close);
            }
        } else if !self.fade_in_done {
            self.alpha = (self.alpha + dt / 0.2).min(1.0);
            self.set_window_alpha();
            if self.alpha >= 1.0 {
                self.fade_in_done = true;
                log::info!("Fade in complete, starting installation");
                self.start_installation(ctx);
            }
        }

        if self.launch_done_at.is_some_and(|t| now >= t) {
            self.launch_done_at = None;
            self.set_step(2, Step::Done);
        }
        if self.auto_close_at.is_some_and(|t| now >= t) {
            self.auto_close_at = None;
            self.close();
        }

        // Ease the bar towards the target value
        if self.animating && !self.indeterminate {
            let diff = self.target - self.shown;
            if diff.abs() < 0.002 {
                self.shown = self.target;
                self.animating = false;
            } else {
                self.shown += diff * (1.0 - 0.82f32.powf(dt / 0.016));
            }
            self.percentage = format!("{}%", (self.shown * 100.0).round() as i32);
        }
    }

    fn set_window_alpha(&self) {
        if let Some(h) = self.hwnd {
            win::set_alpha(h, self.alpha);
        }
    }

    fn schedule_repaint(&self, ctx: &egui::Context) {
        let animating = self.closing
            || !self.fade_in_done
            || self.animating
            || self.indeterminate
            || self.steps.contains(&Step::Active);
        if animating {
            ctx.request_repaint();
            return;
        }
        let now = Instant::now();
        let mut next = [self.launch_done_at, self.auto_close_at]
            .into_iter()
            .flatten()
            .map(|t| t.saturating_duration_since(now))
            .min();
        if self.logs.is_some() {
            let poll = Duration::from_millis(500);
            next = Some(next.map_or(poll, |n| n.min(poll)));
        }
        if let Some(d) = next {
            ctx.request_repaint_after(d);
        }
    }

    // ------------------------------------------------------------------ //
    // Drawing
    // ------------------------------------------------------------------ //
    fn draw(&mut self, ui: &mut Ui) {
        let ctx = ui.ctx().clone();
        let c = self.c;
        let p = ui.painter().clone();

        let footer_top = HEIGHT - 10.0 - FOOTER_HEIGHT;
        let card_top = footer_top - 6.0 - CARD_HEIGHT;
        let left = HERO_WIDTH + PAD_X;
        let right = WIDTH - PAD_X;

        // Drag zones first, so buttons placed later take priority
        let hero_rect = Rect::from_min_size(Pos2::ZERO, vec2(HERO_WIDTH, HEIGHT));
        let top_rect = Rect::from_min_max(pos2(HERO_WIDTH, 0.0), pos2(WIDTH, card_top));
        for (i, r) in [hero_rect, top_rect].into_iter().enumerate() {
            let resp = ui.interact(r, Id::new(("drag", i)), Sense::drag());
            if resp.drag_started_by(PointerButton::Primary) {
                ctx.send_viewport_cmd(ViewportCommand::StartDrag);
            }
        }

        self.draw_hero(&p, hero_rect);
        self.draw_title_bar(ui, &ctx);

        // Heading, description and steps
        p.text(pos2(left, 52.0), Align2::LEFT_CENTER,
            format!("STEP {} OF {}", self.eyebrow_step + 1, STEPS.len()),
            font(11.0, Weight::Semibold), c.accent);
        p.text(pos2(left, 79.5), Align2::LEFT_CENTER, &self.heading, font(26.0, Weight::Bold), c.text);

        let sub = p.layout(self.subtitle_text(), font(13.0, Weight::Regular), c.text_muted, 460.0);
        let sub_top = 103.0;
        let sub_h = sub.size().y.max(28.0);
        p.galley(pos2(left, sub_top + (sub_h - sub.size().y) / 2.0), sub, c.text_muted);

        let steps_top = sub_top + sub_h + 26.0;
        self.draw_steps(&p, pos2(left, steps_top));

        // Progress card
        let card = Rect::from_min_max(pos2(left, card_top), pos2(right, card_top + CARD_HEIGHT));
        self.draw_card(&p, card);

        // Footer
        let fy = footer_top + FOOTER_HEIGHT / 2.0;
        let logs_font = font(12.0, Weight::Regular);
        let logs_w = text_width(&p, "View logs", &logs_font) + 24.0;
        let logs_rect = Rect::from_center_size(pos2(left + logs_w / 2.0, fy), vec2(logs_w, 34.0));
        if button(ui, "logs", logs_rect, "View logs", logs_font, Color32::TRANSPARENT,
            c.surface_alt, c.text_muted, 8)
        {
            self.show_logs(&ctx);
        }

        let sec_rect = Rect::from_center_size(pos2(right - 48.0, fy), vec2(96.0, 36.0));
        if button(ui, "secondary", sec_rect, self.secondary_label, font(13.0, Weight::Regular),
            c.surface_alt, c.surface_hover, c.text, 10)
        {
            self.close();
        }

        if self.show_retry {
            let retry_rect =
                Rect::from_center_size(pos2(sec_rect.left() - 10.0 - 55.0, fy), vec2(110.0, 36.0));
            if button(ui, "retry", retry_rect, "Try again", font(13.0, Weight::Semibold),
                c.accent, c.accent_hover, Color32::WHITE, 10)
            {
                self.retry(&ctx);
            }
        }
    }

    fn draw_hero(&self, p: &Painter, rect: Rect) {
        p.image(self.hero.id(), rect, Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)), Color32::WHITE);

        let layout = theme::hero_layout(HEIGHT);
        let cx = rect.center().x;
        let below = layout.logo_center_y + layout.ring / 2.0;
        p.text(pos2(cx, below + 44.0), Align2::CENTER_CENTER, "Ascendara",
            font(30.0, Weight::Bold), theme::hex(0x2B1B4D));
        p.text(pos2(cx, below + 76.0), Align2::CENTER_CENTER, "Setup",
            font(14.0, Weight::Regular), theme::hex(0x8A73C4));

        let year = chrono::Local::now().format("%Y");
        p.text(pos2(cx, HEIGHT - 28.0), Align2::CENTER_CENTER,
            format!("Installer v{VERSION}  ·  © {year} Ascendara"),
            font(11.0, Weight::Regular), theme::hex(0xA898CF));
    }

    fn draw_title_bar(&mut self, ui: &mut Ui, ctx: &egui::Context) {
        let c = self.c;
        let close_rect = Rect::from_min_size(pos2(WIDTH - 46.0, 0.0), vec2(46.0, 40.0));
        let min_rect = close_rect.translate(vec2(-46.0, 0.0));

        let close = ui.interact(close_rect, Id::new("caption-close"), Sense::click());
        let minimize = ui.interact(min_rect, Id::new("caption-min"), Sense::click());
        let p = ui.painter();

        if close.hovered() {
            p.rect_filled(close_rect, CornerRadius::ZERO, c.close_hover);
        }
        let glyph = Stroke::new(1.0_f32, if close.hovered() { Color32::WHITE } else { c.text_muted });
        let ctr = close_rect.center();
        p.line_segment([ctr + vec2(-5.0, -5.0), ctr + vec2(5.0, 5.0)], glyph);
        p.line_segment([ctr + vec2(-5.0, 5.0), ctr + vec2(5.0, -5.0)], glyph);

        if minimize.hovered() {
            p.rect_filled(min_rect, CornerRadius::ZERO, c.surface_alt);
        }
        let ctr = min_rect.center();
        p.line_segment([ctr + vec2(-5.0, 0.0), ctr + vec2(5.0, 0.0)], Stroke::new(1.0_f32, c.text_muted));

        if close.clicked() {
            self.close();
        }
        if minimize.clicked() {
            ctx.send_viewport_cmd(ViewportCommand::Minimized(true));
        }
    }

    fn draw_steps(&self, p: &Painter, origin: Pos2) {
        let c = self.c;
        let spin = (self.spinner_t0.elapsed().as_secs_f32() / SPINNER_PERIOD).fract();
        for (i, ((title, caption), state)) in STEPS.iter().zip(self.steps).enumerate() {
            let row_top = origin.y + i as f32 * (34.0 + 22.0);
            let icon_center = pos2(origin.x + 12.0, row_top + 2.0 + 12.0);
            draw_step_icon(p, icon_center, state, &c, spin);

            let (title_color, cap_color) = match state {
                Step::Pending => (c.text_subtle, c.text_subtle),
                Step::Error => (c.error, c.text_muted),
                _ => (c.text, c.text_muted),
            };
            let tx = origin.x + 24.0 + 14.0;
            p.text(pos2(tx, row_top + 9.0), Align2::LEFT_CENTER, *title,
                font(13.0, Weight::Semibold), title_color);
            p.text(pos2(tx, row_top + 26.0), Align2::LEFT_CENTER, *caption,
                font(12.0, Weight::Regular), cap_color);

            if i < STEPS.len() - 1 {
                let line = Rect::from_min_max(
                    pos2(origin.x + 11.0, row_top + 34.0 + 4.0),
                    pos2(origin.x + 13.0, row_top + 34.0 + 18.0),
                );
                let color = if state == Step::Done { c.accent } else { c.border };
                p.rect_filled(line, CornerRadius::same(1), color);
            }
        }
    }

    fn draw_card(&self, p: &Painter, card: Rect) {
        let c = self.c;
        p.rect_filled(card, CornerRadius::same(14), c.surface);
        p.rect_stroke(card, CornerRadius::same(14), Stroke::new(1.0_f32, c.border), StrokeKind::Inside);

        let (l, r) = (card.left() + 20.0, card.right() - 20.0);
        let row = card.top() + 30.0;
        p.text(pos2(l, row), Align2::LEFT_CENTER, &self.status, font(13.0, Weight::Semibold), c.text);
        p.text(pos2(r, row), Align2::RIGHT_CENTER, &self.percentage,
            font(13.0, Weight::Semibold), self.percentage_color);

        // Progress bar
        let track = Rect::from_min_max(pos2(l, card.top() + 56.0), pos2(r, card.top() + 62.0));
        p.rect_filled(track, CornerRadius::same(3), c.surface_alt);
        let (start, end) = if self.indeterminate {
            // Same motion as CTkProgressBar: a 40% segment swinging back and forth
            let t = self.indeterminate_t0.elapsed().as_secs_f32();
            let v = ((t / 2.0 * TAU).sin() + 1.0) / 2.0;
            ((v - 0.2).max(0.0), (v + 0.2).min(1.0))
        } else {
            (0.0, self.shown)
        };
        if end - start > 0.0005 {
            let fill = Rect::from_min_max(
                pos2(track.left() + track.width() * start, track.top()),
                pos2(track.left() + track.width() * end, track.bottom()),
            );
            p.rect_filled(fill, CornerRadius::same(3), self.bar_color);
        }

        p.text(pos2(l, card.top() + 79.0), Align2::LEFT_CENTER, &self.detail,
            font(12.0, Weight::Regular), c.text_subtle);
    }
}

impl eframe::App for InstallerApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.drain_messages();
        self.tick(ctx);

        // Alt+F4 / taskbar close: fade out instead of closing immediately
        if ctx.input(|i| i.viewport().close_requested()) && !self.close_sent {
            ctx.send_viewport_cmd(ViewportCommand::CancelClose);
            self.close();
        }

        egui::CentralPanel::default()
            .frame(egui::Frame::NONE.fill(self.c.bg))
            .show(ctx, |ui| self.draw(ui));

        if let Some(lw) = &mut self.logs {
            if !lw.show(ctx, &self.c, self.dark, &self.icon) {
                self.logs = None;
                log::info!("Log window closed");
            }
        }

        self.schedule_repaint(ctx);
    }
}

// ---------------------------------------------------------------------- //
// Widgets
// ---------------------------------------------------------------------- //
fn text_width(p: &Painter, text: &str, font: &FontId) -> f32 {
    p.layout_no_wrap(text.to_owned(), font.clone(), Color32::WHITE).size().x
}

#[allow(clippy::too_many_arguments)]
pub fn button(
    ui: &mut Ui,
    id: &str,
    rect: Rect,
    label: &str,
    font: FontId,
    fill: Color32,
    hover_fill: Color32,
    text: Color32,
    radius: u8,
) -> bool {
    let resp = ui
        .interact(rect, Id::new(("button", id)), Sense::click())
        .on_hover_cursor(CursorIcon::PointingHand);
    let bg = if resp.hovered() { hover_fill } else { fill };
    if bg.a() > 0 {
        ui.painter().rect_filled(rect, CornerRadius::same(radius), bg);
    }
    ui.painter().text(rect.center(), Align2::CENTER_CENTER, label, font, text);
    resp.clicked()
}

/// Step indicator: pending ring, active spinner, done check or error cross.
fn draw_step_icon(p: &Painter, center: Pos2, state: Step, c: &Palette, spin: f32) {
    const R: f32 = 11.0;
    let at = |fx: f32, fy: f32| center + vec2((fx - 0.5) * 24.0, (fy - 0.5) * 24.0);
    match state {
        Step::Pending => {
            p.circle_stroke(center, R - 1.0, Stroke::new(2.0_f32, c.border));
        }
        Step::Active => {
            p.circle_filled(center, R, c.accent_soft);
            let start = spin * TAU;
            let sweep = 100f32.to_radians();
            let points: Vec<Pos2> = (0..=24)
                .map(|k| {
                    let a = start + sweep * k as f32 / 24.0;
                    center + vec2(a.cos(), a.sin()) * (R - 1.0)
                })
                .collect();
            p.add(Shape::line(points, Stroke::new(2.0_f32, c.accent)));
            p.circle_filled(center, 3.0, c.accent);
        }
        Step::Done => {
            p.circle_filled(center, R, c.accent);
            p.add(Shape::line(
                vec![at(0.30, 0.52), at(0.44, 0.66), at(0.71, 0.38)],
                Stroke::new(2.2_f32, Color32::WHITE),
            ));
        }
        Step::Error => {
            p.circle_filled(center, R, c.error);
            let s = Stroke::new(2.2_f32, Color32::WHITE);
            p.line_segment([at(0.36, 0.36), at(0.64, 0.64)], s);
            p.line_segment([at(0.36, 0.64), at(0.64, 0.36)], s);
        }
    }
}
