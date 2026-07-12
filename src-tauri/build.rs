fn main() {
    let mut windows = tauri_build::WindowsAttributes::new();
    
    // Define the manifest with requireAdministrator and Microsoft.Windows.Common-Controls
    let manifest = r#"
        <assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
            <dependency>
                <dependentAssembly>
                    <assemblyIdentity
                        type="win32"
                        name="Microsoft.Windows.Common-Controls"
                        version="6.0.0.0"
                        processorArchitecture="*"
                        publicKeyToken="6595b64144ccf1df"
                        language="*"
                    />
                </dependentAssembly>
            </dependency>
            <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
                <security>
                    <requestedPrivileges>
                        <requestedExecutionLevel level="requireAdministrator" uiAccess="false" />
                    </requestedPrivileges>
                </security>
            </trustInfo>
        </assembly>
    "#;

    windows = windows.app_manifest(manifest);

    tauri_build::try_build(
        tauri_build::Attributes::new().windows_attributes(windows)
    ).expect("failed to run build script");

    // Automatically copy WinDivert binaries and db.json to target directory for direct development/testing
    if let Ok(out_dir) = std::env::var("OUT_DIR") {
        let out_path = std::path::PathBuf::from(out_dir);
        if let Some(target_dir) = out_path.parent().and_then(|p| p.parent()).and_then(|p| p.parent()) {
            let src_dir = std::path::PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
            
            let dll_src = src_dir.join("WinDivert.dll");
            let sys_src = src_dir.join("WinDivert64.sys");
            let db_src = src_dir.join("db.json");
            
            let dll_dest = target_dir.join("WinDivert.dll");
            let sys_dest = target_dir.join("WinDivert64.sys");
            let db_dest = target_dir.join("db.json");
            
            if dll_src.exists() {
                let _ = std::fs::copy(&dll_src, &dll_dest);
            }
            if sys_src.exists() {
                let _ = std::fs::copy(&sys_src, &sys_dest);
            }
            if db_src.exists() {
                let _ = std::fs::copy(&db_src, &db_dest);
            }
        }
    }
}
