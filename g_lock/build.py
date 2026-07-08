import os
import re
import sys

import PyInstaller.__main__


def bump_version(current: str, part: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def update_version_txt(version_path: str, new_version: str) -> None:
    if not os.path.exists(version_path):
        return
    with open(version_path, "r", encoding="utf-8") as f:
        content = f.read()

    major, minor, patch = new_version.split(".")
    # Replace tuple representations: e.g. filevers=(1, 0, 0, 0)
    content = re.sub(
        r"filevers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)",
        f"filevers=({major}, {minor}, {patch}, 0)",
        content,
    )
    content = re.sub(
        r"prodvers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)",
        f"prodvers=({major}, {minor}, {patch}, 0)",
        content,
    )
    # Replace StringStruct representation: e.g. StringStruct('FileVersion', '1.0.0')
    content = re.sub(
        r"StringStruct\('FileVersion',\s*'[^']+'\)",
        f"StringStruct('FileVersion', '{new_version}')",
        content,
    )
    content = re.sub(
        r"StringStruct\('ProductVersion',\s*'[^']+'\)",
        f"StringStruct('ProductVersion', '{new_version}')",
        content,
    )

    with open(version_path, "w", encoding="utf-8") as f:
        f.write(content)


def build() -> None:
    # 1. Parse command line arguments to determine version bump type
    bump_type = "patch"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("major", "minor", "patch"):
            bump_type = arg

    # 2. Read and bump version in g_lock/__version__.py
    version_file = os.path.join("g_lock", "__version__.py")
    current_version = "1.0.0"
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
            if match:
                current_version = match.group(1)

    new_version = bump_version(current_version, bump_type)
    print(f"Bumping G-Lock version: {current_version} -> {new_version} ({bump_type})")

    # 3. Write back to __version__.py
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(f'__version__ = "{new_version}"\n')

    # 4. Update spec/version.txt
    update_version_txt(os.path.join("spec", "version.txt"), new_version)

    # 5. Run PyInstaller build
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
            "G-Lock",
            "--version-file",
            "version.txt",
            "--specpath",
            "spec",
        )
    )


if __name__ == "__main__":
    build()
