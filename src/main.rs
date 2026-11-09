#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod app;
mod installer;
mod log_window;
mod logging;
mod theme;
mod win;

use eframe::egui;

/// Installer version, shown in the hero footer.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() -> eframe::Result {
    logging::setup();
    log::info!("Application started");
    log::info!("Initializing Ascendara Installer");

    let icon = std::sync::Arc::new(theme::window_icon());
    let logo = theme::load_logo();

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Ascendara Installer")
            .with_inner_size([app::WIDTH, app::HEIGHT])
            .with_resizable(false)
            .with_maximize_button(false)
            .with_decorations(false) // frameless window
            .with_icon(icon.clone()),
        centered: true,
        renderer: eframe::Renderer::Wgpu,
        wgpu_options: wgpu_options(),
        ..Default::default()
    };

    let result = eframe::run_native(
        "Ascendara Installer",
        options,
        Box::new(move |cc| Ok(Box::new(app::InstallerApp::new(cc, icon, logo)))),
    );
    if let Err(e) = &result {
        log::error!("Application error: {e}");
    }
    result
}

/// Renderer setup: DirectX 12 first (with the WARP software rasterizer as a
/// last resort, so GPU-less VMs and basic display drivers still work).
fn wgpu_options() -> eframe::egui_wgpu::WgpuConfiguration {
    use eframe::egui_wgpu::{wgpu, WgpuConfiguration, WgpuSetup, WgpuSetupCreateNew};
    use wgpu::DeviceType;

    let mut setup = WgpuSetupCreateNew::default();
    setup.instance_descriptor.backends = wgpu::Backends::DX12;
    setup.power_preference = wgpu::PowerPreference::LowPower;
    setup.native_adapter_selector = Some(std::sync::Arc::new(|adapters, surface| {
        let rank = |a: &wgpu::Adapter| {
            // Prefer a real GPU (integrated first, it's plenty), WARP last
            match a.get_info().device_type {
                DeviceType::IntegratedGpu => 0,
                DeviceType::DiscreteGpu => 1,
                DeviceType::VirtualGpu | DeviceType::Other => 2,
                DeviceType::Cpu => 3,
            }
        };
        let adapter = adapters
            .iter()
            .filter(|a| surface.is_none_or(|s| a.is_surface_supported(s)))
            .min_by_key(|a| rank(a))
            .cloned()
            .ok_or_else(|| "No suitable graphics adapter found".to_owned())?;
        let info = adapter.get_info();
        log::info!("Graphics adapter: {} ({:?}, {:?})", info.name, info.backend, info.device_type);
        Ok(adapter)
    }));

    WgpuConfiguration { wgpu_setup: WgpuSetup::CreateNew(setup), ..Default::default() }
}
