import PyInstaller.__main__

version = "1.0.0"


def build() -> None:
    PyInstaller.__main__.run(
        (
            "g_lock\\__main__.py",
            "--onefile",
            "--icon",
            "logo.ico",
            "--add-data",
            "..\\db.json;.",
            "--uac-admin",
            "--name",
            f"G-Lock-{version}",
            "--version-file",
            "version.txt",
            "--specpath",
            "spec",
        )
    )
