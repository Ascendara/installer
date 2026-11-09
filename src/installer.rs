//! Download and run the Ascendara setup on a background thread.

use std::fs::{self, File};
use std::io::{BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::mpsc::Sender;
use std::time::Duration;

use anyhow::{anyhow, bail, Context as _, Result};
use eframe::egui;

pub const VERSION_URL: &str = "https://api.ascendara.app/";
const GITHUB_LATEST: &str = "https://api.github.com/repos/Ascendara/ascendara/releases/latest";

// Chrome-like UA for better compatibility with download mirrors
const CHROME_UA: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
     (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36";

pub enum Msg {
    /// `None` = indeterminate, otherwise a fraction in 0..=1.
    Progress(Option<f32>),
    Status(String),
    Complete(bool),
}

/// Sends installer events to the UI, tagged with the run generation so
/// messages from a stale run can be ignored.
#[derive(Clone)]
pub struct Reporter {
    pub tx: Sender<(u64, Msg)>,
    pub generation: u64,
    pub ctx: egui::Context,
}

impl Reporter {
    fn send(&self, msg: Msg) {
        let _ = self.tx.send((self.generation, msg));
        self.ctx.request_repaint();
    }
    fn progress(&self, p: Option<f32>) {
        self.send(Msg::Progress(p));
    }
    fn status(&self, s: impl Into<String>) {
        self.send(Msg::Status(s.into()));
    }
    fn complete(&self, ok: bool) {
        self.send(Msg::Complete(ok));
    }
}

fn api_agent(timeout: Duration) -> ureq::Agent {
    ureq::AgentBuilder::new().timeout(timeout).build()
}

/// `appVer` from api.ascendara.app, if the API reports status OK.
fn fetch_ok_app_version(timeout: Duration) -> Result<Option<String>> {
    let data: serde_json::Value = api_agent(timeout).get(VERSION_URL).call()?.into_json()?;
    if data.get("status").and_then(|s| s.as_str()) != Some("OK") {
        return Ok(None);
    }
    Ok(json_str(&data, "appVer"))
}

/// `appVer` from api.ascendara.app (no status check), used for display only.
pub fn fetch_display_version() -> Result<Option<String>> {
    let data: serde_json::Value = api_agent(Duration::from_secs(5))
        .get(VERSION_URL)
        .call()?
        .into_json()?;
    Ok(json_str(&data, "appVer"))
}

fn json_str(v: &serde_json::Value, key: &str) -> Option<String> {
    match v.get(key)? {
        serde_json::Value::String(s) if !s.is_empty() => Some(s.clone()),
        serde_json::Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

pub fn spawn(rep: Reporter) -> std::io::Result<()> {
    std::thread::Builder::new()
        .name("installer".into())
        .spawn(move || run(&rep))
        .map(|_| ())
}

fn run(rep: &Reporter) {
    log::info!("Starting installation process");
    rep.progress(None);

    // Primary: version from api.ascendara.app + direct GitHub download URL
    match primary(rep) {
        Ok(true) => return,
        Ok(false) => {}
        Err(e) => {
            log::error!("Primary download failed: {e:#}");
            rep.status("Primary download failed, trying backup...");
        }
    }

    // Fallback: find the setup in GitHub's latest release, in case the API is down
    if let Err(e) = backup(rep) {
        log::error!("Backup download failed: {e:#}");
        rep.status("Download failed. Please try again later.");
        rep.complete(false);
    }
}

/// Returns Ok(false) when the API didn't give a usable version (fall through
/// to the backup silently), Ok(true) once installation succeeded.
fn primary(rep: &Reporter) -> Result<bool> {
    let Some(version) = fetch_ok_app_version(Duration::from_secs(5))? else {
        return Ok(false);
    };
    let url = format!(
        "https://github.com/tagoWorks/ascendara/releases/download/{version}/Ascendara.Setup.{version}.exe"
    );
    let path = std::env::temp_dir().join(format!("AscendaraInstaller_{version}.exe"));
    rep.status("Downloading Ascendara...");
    download_and_install(rep, &url, &path)?;
    Ok(true)
}

fn backup(rep: &Reporter) -> Result<()> {
    let release: serde_json::Value = api_agent(Duration::from_secs(15))
        .get(GITHUB_LATEST)
        .set("Accept", "application/vnd.github+json")
        .call()?
        .into_json()?;
    let url = release
        .get("assets")
        .and_then(|a| a.as_array())
        .into_iter()
        .flatten()
        .find_map(|asset| {
            let name = asset.get("name")?.as_str()?;
            (name.starts_with("Ascendara.Setup.") && name.ends_with(".exe"))
                .then(|| asset.get("browser_download_url")?.as_str().map(str::to_owned))?
        })
        .ok_or_else(|| anyhow!("No installer found in latest release"))?;

    rep.status("Downloading Ascendara...");
    let path = std::env::temp_dir().join("AscendaraInstaller.exe");
    download_and_install(rep, &url, &path)
}

fn download_and_install(rep: &Reporter, url: &str, path: &Path) -> Result<()> {
    let local = download_file(rep, url, path)?;
    if fs::metadata(&local).map(|m| m.len()).unwrap_or(0) == 0 {
        bail!("Download verification failed");
    }

    rep.status("Running installer...");
    rep.progress(None); // switch to indeterminate mode

    // Dev aid: debug builds can skip actually running the downloaded setup
    let skip = cfg!(debug_assertions) && std::env::var_os("ASCENDARA_SKIP_SETUP").is_some();
    let code = if skip {
        log::warn!("ASCENDARA_SKIP_SETUP set, not running {}", local.display());
        std::thread::sleep(Duration::from_secs(3));
        0
    } else {
        run_setup(&local)?
    };
    if code != 0 {
        bail!("Installation failed with code {code}");
    }
    rep.status("Installation complete!");
    rep.complete(true);
    Ok(())
}

/// Download `url` to `path`, reporting progress.
fn download_file(rep: &Reporter, url: &str, path: &Path) -> Result<PathBuf> {
    let result = (|| -> Result<PathBuf> {
        if let Some(dir) = path.parent() {
            fs::create_dir_all(dir)?;
        }
        log::info!("Downloading file from {url} to {}", path.display());
        let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        rep.status(format!("Downloading {name}..."));

        let agent = ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(30))
            .timeout_read(Duration::from_secs(30))
            .build();
        let resp = agent
            .get(url)
            .set("User-Agent", CHROME_UA)
            .set("Accept", "*/*")
            .call()?;
        let total: u64 = resp
            .header("content-length")
            .and_then(|v| v.parse().ok())
            .unwrap_or(0);

        let mut reader = resp.into_reader();
        let mut file = BufWriter::with_capacity(1 << 20, File::create(path)?);
        let mut buf = vec![0u8; 1 << 20];
        let mut downloaded: u64 = 0;
        let mut last_reported = -1.0f32;
        loop {
            let n = reader.read(&mut buf)?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])?;
            downloaded += n as u64;
            if total > 0 {
                let p = (downloaded as f32 / total as f32).min(1.0);
                if p - last_reported >= 0.002 || downloaded >= total {
                    last_reported = p;
                    rep.progress(Some(p));
                }
            }
        }
        file.flush()?;
        log::info!("Download completed: {}", path.display());
        Ok(path.to_path_buf())
    })();

    if let Err(e) = &result {
        log::error!("Download failed: {e:#}");
        rep.status(format!("Download error: {e}"));
    }
    result
}

/// Run the setup through the shell (like `shell=True`) so elevation prompts
/// are handled, and wait for it to exit.
#[cfg(windows)]
fn run_setup(path: &Path) -> Result<i32> {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let status = std::process::Command::new("cmd.exe")
        .arg("/C")
        .raw_arg(format!("\"\"{}\"\"", path.display()))
        .creation_flags(CREATE_NO_WINDOW)
        .status()
        .context("could not start the setup")?;
    Ok(status.code().unwrap_or(-1))
}

#[cfg(not(windows))]
fn run_setup(path: &Path) -> Result<i32> {
    let status = std::process::Command::new(path).status()?;
    Ok(status.code().unwrap_or(-1))
}
