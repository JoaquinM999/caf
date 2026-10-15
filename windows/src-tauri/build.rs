fn main() {
    #[cfg(target_env = "msvc")]
    {
        cc::Build::new()
            .file("src/msvc_compat.c")
            .static_crt(true)
            .compile("msvc_compat_c");

        cc::Build::new()
            .cpp(true)
            .file("src/msvc_compat_tables.cpp")
            .static_crt(true)
            .compile("msvc_compat_cpp");
    }
    tauri_build::build();
}
