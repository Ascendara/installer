//! Separate native window showing live installer logs.

use std::sync::Arc;
use std::time::{Duration, Instant};

use eframe::egui::{
    self, pos2, text::LayoutJob, vec2, Align2, Color32, CornerRadius, Pos2, Rect, Stroke,
    StrokeKind, TextFormat, Ui, UiBuilder, ViewportBuilder, ViewportCommand, ViewportId,
};

use crate::app::button;
use crate::logging;
use crate::theme::{font, Palette, Weight};
use crate::win;

const TITLE: &str = "Ascendara Installer Logs";

struct Rendered {
    revision: u64,
    job: LayoutJob,
    lines: usize,
}

pub struct LogWindow {
    id: ViewportId,
    position: Option<Pos2>,
    styled: bool,
    focus: bool,
    flash: Option<(String, Instant)>,
    rendered: Option<Rendered>,
}

impl LogWindow {
    pub fn new(position: Option<Pos2>) -> Self {
        log::info!("Log window created");
        Self {
            id: ViewportId::from_hash_of("installer-logs"),
            position,
            styled: false,
            focus: true,
            flash: None,
            rendered: None,
        }
    }

    pub fn focus(&mut self) {
        self.focus = true;
    }

    /// Draw the window for this frame. Returns false once the user closed it.
    pub fn show(&mut self, ctx: &egui::Context, c: &Palette, dark: bool, icon: &Arc<egui::IconData>) -> bool {
        let mut builder = ViewportBuilder::default()
            .with_title(TITLE)
            .with_inner_size([820.0, 520.0])
            .with_min_inner_size([640.0, 380.0])
            .with_icon(icon.clone());
        if let Some(p) = self.position {
            builder = builder.with_position(p);
        }

        let mut open = true;
        ctx.show_viewport_immediate(self.id, builder, |ctx, _class| {
            if ctx.input(|i| i.viewport().close_requested()) {
                open = false;
            }
            if !self.styled {
                if let Some(h) = win::find_window(TITLE) {
                    win::dark_title_bar(h, dark);
                    self.styled = true;
                }
            }
            if self.focus {
                ctx.send_viewport_cmd(ViewportCommand::Focus);
                self.focus = false;
            }
            egui::CentralPanel::default()
                .frame(egui::Frame::NONE.fill(c.bg))
                .show(ctx, |ui| self.ui(ui, c));
            if let Some((_, t)) = &self.flash {
                ctx.request_repaint_after(Duration::from_millis(2500).saturating_sub(t.elapsed()));
            }
        });
        open
    }

    fn refresh(&mut self, c: &Palette) {
        let revision = logging::revision();
        if self.rendered.as_ref().is_some_and(|r| r.revision == revision) {
            return;
        }
        let content = logging::snapshot();
        self.rendered = Some(Rendered {
            revision,
            job: colorize(&content, c),
            lines: content.lines().count(),
        });
    }

    fn flash(&mut self, text: &str) {
        self.flash = Some((text.to_owned(), Instant::now()));
    }

    fn ui(&mut self, ui: &mut Ui, c: &Palette) {
        self.refresh(c);
        let p = ui.painter().clone();
        let full = ui.max_rect();
        let inner = Rect::from_min_max(full.min + vec2(20.0, 16.0), full.max - vec2(20.0, 20.0));

        // Header
        p.text(pos2(inner.left(), inner.top() + 12.0), Align2::LEFT_CENTER, "Installer logs",
            font(18.0, Weight::Bold), c.text);
        p.text(pos2(inner.left(), inner.top() + 32.0), Align2::LEFT_CENTER,
            "Live output from this setup session", font(12.0, Weight::Regular), c.text_muted);

        let lines = self.rendered.as_ref().map_or(0, |r| r.lines);
        let chip_text = format!("{lines} line{}", if lines == 1 { "" } else { "s" });
        let chip_galley = p.layout_no_wrap(chip_text, font(11.0, Weight::Semibold), c.accent);
        let chip = Rect::from_min_size(
            pos2(inner.right() - chip_galley.size().x - 20.0, inner.top() + 2.0),
            vec2(chip_galley.size().x + 20.0, 22.0),
        );
        p.rect_filled(chip, CornerRadius::same(10), c.accent_soft);
        p.galley(chip.center() - chip_galley.size() / 2.0, chip_galley, c.accent);

        // Log text
        let footer_top = inner.bottom() - 34.0;
        let text_box = Rect::from_min_max(
            pos2(inner.left(), inner.top() + 40.0 + 12.0),
            pos2(inner.right(), footer_top - 14.0),
        );
        p.rect_filled(text_box, CornerRadius::same(12), c.surface);
        p.rect_stroke(text_box, CornerRadius::same(12), Stroke::new(1.0_f32, c.border), StrokeKind::Inside);

        let job = self.rendered.as_ref().map(|r| r.job.clone()).unwrap_or_default();
        ui.scope_builder(UiBuilder::new().max_rect(text_box.shrink(8.0)), |ui| {
            egui::ScrollArea::both()
                .auto_shrink([false, false])
                .stick_to_bottom(true)
                .show(ui, |ui| {
                    ui.add(egui::Label::new(job).selectable(true).wrap_mode(egui::TextWrapMode::Extend));
                });
        });

        // Footer
        let fy = footer_top + 17.0;
        let mut x = inner.left();
        let mut next = |w: f32| {
            let r = Rect::from_min_size(pos2(x, footer_top), vec2(w, 34.0));
            x += w + 8.0;
            r
        };
        let (copy_r, folder_r, clear_r) = (next(104.0), next(126.0), next(72.0));

        if button(ui, "log-copy", copy_r, "Copy logs", font(12.0, Weight::Semibold),
            c.accent, c.accent_hover, Color32::WHITE, 9)
        {
            ui.ctx().copy_text(logging::snapshot());
            self.flash("Copied to clipboard");
        }
        if button(ui, "log-folder", folder_r, "Open log folder", font(12.0, Weight::Regular),
            c.surface_alt, c.surface_hover, c.text, 9)
        {
            if let Err(e) = open_log_folder() {
                log::error!("Could not open log folder: {e}");
                self.flash("Couldn't open folder");
            }
        }
        if button(ui, "log-clear", clear_r, "Clear", font(12.0, Weight::Regular),
            Color32::TRANSPARENT, c.surface_alt, c.text_muted, 9)
        {
            logging::clear();
            self.refresh(c);
            self.flash("Logs cleared");
        }

        if self.flash.as_ref().is_some_and(|(_, t)| t.elapsed() >= Duration::from_millis(2500)) {
            self.flash = None;
        }
        if let Some((text, _)) = &self.flash {
            p.text(pos2(inner.right(), fy), Align2::RIGHT_CENTER, text,
                font(12.0, Weight::Regular), c.text_muted);
        }
    }
}

fn open_log_folder() -> std::io::Result<()> {
    let dir = logging::log_dir();
    std::fs::create_dir_all(&dir)?;
    std::process::Command::new("explorer").arg(&dir).spawn().map(|_| ())
}

/// Parse `HH:MM:SS - LEVEL - ` prefixes; returns (time, level, rest).
fn split_line(line: &str) -> Option<(&str, &str, &str)> {
    let b = line.as_bytes();
    let time_ok = b.len() > 11
        && [0, 1, 3, 4, 6, 7].iter().all(|&i| b[i].is_ascii_digit())
        && b[2] == b':'
        && b[5] == b':'
        && &line[8..11] == " - ";
    if !time_ok {
        return None;
    }
    let after = &line[11..];
    let end = after.find(" - ")?;
    let level = &after[..end];
    if level.is_empty() || !level.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'_') {
        return None;
    }
    Some((&line[..8], level, &after[end + 3..]))
}

/// Colour log lines: dim timestamps, amber warnings, red errors.
fn colorize(content: &str, c: &Palette) -> LayoutJob {
    let mono = egui::FontId::monospace(12.0);
    let fmt = |color: Color32| TextFormat { font_id: mono.clone(), color, ..Default::default() };
    let mut job = LayoutJob::default();
    let mut level = "";
    for line in content.lines() {
        if let Some((time, lvl, rest)) = split_line(line) {
            level = lvl;
            let color = match lvl {
                "ERROR" | "CRITICAL" => c.log_error,
                "WARNING" => c.log_warn,
                _ => c.log_info,
            };
            job.append(&format!("{time}  "), 0.0, fmt(c.log_time));
            job.append(&format!("{rest}\n"), 0.0, fmt(color));
        } else {
            // Continuation lines (backtraces) inherit the previous level's colour
            let color = if matches!(level, "ERROR" | "CRITICAL") { c.log_error } else { c.log_info };
            job.append(&format!("{line}\n"), 0.0, fmt(color));
        }
    }
    job
}
