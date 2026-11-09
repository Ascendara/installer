fn main() {
    println!("cargo:rerun-if-changed=ascendara.ico");
    println!("cargo:rerun-if-changed=app.manifest");
    println!("cargo:rerun-if-env-changed=ASCENDARA_REQUIRE_RESOURCES");

    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("ascendara.ico")
            .set_manifest_file("app.manifest")
            .set("ProductName", "Ascendara Installer")
            .set("FileDescription", "Ascendara Installer");
        if let Err(e) = res.compile() {
            // CI sets this so a release never ships without its icon and manifest
            if std::env::var_os("ASCENDARA_REQUIRE_RESOURCES").is_some() {
                panic!("Could not embed Windows resources: {e}");
            }
            println!("cargo:warning=Could not embed Windows resources: {e}");
        }
    }
}
