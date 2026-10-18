fn main() {
    #[cfg(target_env = "msvc")]
    {
        println!("cargo:rerun-if-changed=src/msvc_compat.c");
        println!("cargo:rerun-if-changed=src/msvc_compat_tables.cpp");

        cc::Build::new()
            .file("src/msvc_compat.c")
            .static_crt(true)
            .compile("msvc_compat_c");

        cc::Build::new()
            .cpp(true)
            .flag("/std:c++17")
            .file("src/msvc_compat_tables.cpp")
            .static_crt(true)
            .compile("msvc_compat_cpp");

        println!("cargo:rustc-link-arg=/WHOLEARCHIVE:msvc_compat_c.lib");
        println!("cargo:rustc-link-arg=/WHOLEARCHIVE:msvc_compat_cpp.lib");
    }
    tauri_build::build();
}
