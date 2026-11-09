//! Logging to stdout, an in-memory buffer (for the log window) and a
//! persistent file under %LOCALAPPDATA%\Ascendara\InstallerLogs.

use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, MutexGuard};

static BUFFER: Mutex<String> = Mutex::new(String::new());
static FILE: Mutex<Option<File>> = Mutex::new(None);
/// Bumped on every write/clear so the log window knows when to re-render.
static REVISION: AtomicU64 = AtomicU64::new(0);

fn lock<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// Persistent log location that survives even if the process crashes.
pub fn log_dir() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    base.join("Ascendara").join("InstallerLogs")
}

/// Write one formatted line (`HH:MM:SS - LEVEL - message`) to every sink.
pub fn write(level: &str, msg: &str) {
    let line = format!(
        "{} - {} - {}\n",
        chrono::Local::now().format("%H:%M:%S"),
        level,
        msg
    );
    let _ = std::io::stdout().write_all(line.as_bytes());
    lock(&BUFFER).push_str(&line);
    if let Some(f) = lock(&FILE).as_mut() {
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }
    REVISION.fetch_add(1, Ordering::Relaxed);
}

pub fn snapshot() -> String {
    lock(&BUFFER).clone()
}

pub fn revision() -> u64 {
    REVISION.load(Ordering::Relaxed)
}

/// Clear the in-app log (the file on disk is kept).
pub fn clear() {
    lock(&BUFFER).clear();
    REVISION.fetch_add(1, Ordering::Relaxed);
}

struct Logger;

impl log::Log for Logger {
    fn enabled(&self, m: &log::Metadata) -> bool {
        m.level() <= log::Level::Info && m.target().starts_with(env!("CARGO_CRATE_NAME"))
    }

    fn log(&self, record: &log::Record) {
        if !self.enabled(record.metadata()) {
            return;
        }
        let level = match record.level() {
            log::Level::Error => "ERROR",
            log::Level::Warn => "WARNING",
            log::Level::Info => "INFO",
            log::Level::Debug => "DEBUG",
            log::Level::Trace => "TRACE",
        };
        write(level, &record.args().to_string());
    }

    fn flush(&self) {}
}

static LOGGER: Logger = Logger;

pub fn setup() {
    let _ = log::set_logger(&LOGGER);
    log::set_max_level(log::LevelFilter::Info);

    let dir = log_dir();
    let path = dir.join("installer.log");
    match fs::create_dir_all(&dir)
        .and_then(|_| OpenOptions::new().create(true).append(true).open(&path))
    {
        Ok(f) => {
            *lock(&FILE) = Some(f);
            log::info!("Logging to file: {}", path.display());
        }
        Err(e) => log::warn!("Could not set up file logging: {e}"),
    }

    // Log panics on any thread before the default hook runs, so crashes
    // leave a trace on disk.
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let thread = std::thread::current();
        let name = thread.name().unwrap_or("<unnamed>");
        write(
            "CRITICAL",
            &format!(
                "Unhandled panic in thread {name}:\n{info}\n{}",
                std::backtrace::Backtrace::force_capture()
            ),
        );
        default_hook(info);
    }));
}
