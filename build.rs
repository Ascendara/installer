fn main() {
    println!("cargo:rerun-if-changed=ascendara.ico");
    println!("cargo:rerun-if-changed=app.manifest");

    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("ascendara.ico")
            .set_manifest_file("app.manifest")
            .set("ProductName", "Ascendara Installer")
            .set("FileDescription", "Ascendara Installer");
        if let Err(e) = res.compile() {
            println!("cargo:warning=Could not embed Windows resources: {e}");
        }
    }
}
