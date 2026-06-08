#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║        UltraWater Client — Build & Release Tool         ║
║        v2.0.0                                           ║
╚══════════════════════════════════════════════════════════╝

Automates:
  - Dependency audit & environment validation
  - PyInstaller packaging (Windows/Linux/macOS)
  - Windows installer creation via Inno Setup
  - DMG creation on macOS
  - Version bumping & git tagging
  - GitHub Release asset preparation

Usage:
    python build/build.py all          # Full build for current platform
    python build/build.py exe          # PyInstaller executable only
    python build/build.py installer    # Executable + platform installer
    python build/build.py release      # Full release (build + tag + assets)
    python build/build.py clean        # Remove build artifacts
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple


# ── Configuration ─────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "src"
BUILD = ROOT / "build"
DIST  = ROOT / "dist"
ASSETS = ROOT / "website" / "assets"

APP_NAME = "UltraWater"
EXE_NAME = "UltraWater"
VERSION_FILE = ROOT / "src" / "VERSION"

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"
ARCH       = platform.machine()

# PyInstaller options
PYINSTALLER_OPTS = {
    "windows": [
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", APP_NAME,
        "--icon", str(ASSETS / "icon.ico"),
        "--add-data", f"{SRC / 'VERSION'};.",
        "--noupx",
        "--clean",
    ],
    "linux": [
        "--noconfirm",
        "--onedir",
        "--name", APP_NAME,
        "--add-data", f"{SRC / 'VERSION'}:.",
        "--noupx",
        "--clean",
    ],
    "darwin": [
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", APP_NAME,
        "--icon", str(ASSETS / "icon.icns"),
        "--add-data", f"{SRC / 'VERSION'}:.",
        "--noupx",
        "--clean",
    ],
}


# ── Utilities ─────────────────────────────────────────────

class Colored:
    """Terminal colors for build output."""
    HEADER = '\033[95m'
    BLUE   = '\033[94m'
    CYAN   = '\033[96m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    RED    = '\033[91m'
    END    = '\033[0m'
    BOLD   = '\033[1m'
    DIM    = '\033[2m'

    @classmethod
    def ok(cls, msg):    return f"{cls.GREEN}{msg}{cls.END}"
    @classmethod
    def info(cls, msg):  return f"{cls.CYAN}{msg}{cls.END}"
    @classmethod
    def warn(cls, msg):  return f"{cls.YELLOW}{msg}{cls.END}"
    @classmethod
    def error(cls, msg): return f"{cls.RED}{msg}{cls.END}"
    @classmethod
    def bold(cls, msg):  return f"{cls.BOLD}{msg}{cls.END}"
    @classmethod
    def header(cls, msg): return f"{cls.HEADER}{cls.BOLD}{msg}{cls.END}"


def log(msg: str, level: str = "info"):
    """Print a colored log message."""
    method = getattr(Colored, level, Colored.info)
    prefix = {
        "ok": "  ✓",
        "info": "  •",
        "warn": "  ⚠",
        "error": "  ✗",
        "header": "═══",
    }.get(level, "  •")
    print(f"{method(prefix)} {msg}")


def run(cmd: List[str], cwd: Optional[Path] = None, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command with proper output."""
    log(f"$ {' '.join(cmd)}", "info")
    try:
        result = subprocess.run(
            cmd, cwd=cwd or ROOT,
            capture_output=capture,
            text=True,
            check=True,
        )
        if capture:
            return result
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(Colored.warn(result.stderr))
        return result
    except subprocess.CalledProcessError as e:
        log(f"Command failed with exit code {e.returncode}", "error")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(Colored.error(e.stderr))
        raise


def get_version() -> str:
    """Read the current version from VERSION file."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "0.0.0"


def set_version(version: str):
    """Write version to VERSION file and update __init__ if present."""
    VERSION_FILE.write_text(version.strip() + "\n")
    log(f"Version set to {version}", "ok")


def find_pyinstaller() -> Optional[str]:
    """Locate PyInstaller."""
    return shutil.which("pyinstaller") or shutil.which("pyinstaller.exe")


def find_customtkinter() -> Optional[Path]:
    """Find the customtkinter package directory."""
    try:
        import customtkinter
        return Path(customtkinter.__file__).parent
    except ImportError:
        pass

    # Try pip show
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "customtkinter"],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if line.startswith("Location:"):
                loc = line.split(":", 1)[1].strip()
                p = Path(loc) / "customtkinter"
                if p.exists():
                    return p
    except subprocess.CalledProcessError:
        pass
    return None


# ── Build Steps ───────────────────────────────────────────

def step_environment_check() -> bool:
    """Check that all build prerequisites are met."""
    print(f"\n{Colored.header('═' * 60)}")
    print(f"{Colored.header('  Environment Check')}")
    print(f"{Colored.header('═' * 60)}")
    
    all_ok = True
    
    # Python
    py_ver = sys.version.split()[0]
    log(f"Python {py_ver}", "ok")
    
    # PyInstaller
    pi = find_pyinstaller()
    if pi:
        result = subprocess.run([pi, "--version"], capture_output=True, text=True)
        log(f"PyInstaller {result.stdout.strip()}", "ok")
    else:
        log("PyInstaller not found! Install: pip install pyinstaller", "error")
        all_ok = False
    
    # customtkinter
    ctk = find_customtkinter()
    if ctk:
        log(f"customtkinter at {ctk}", "ok")
    else:
        log("customtkinter not found! Install: pip install customtkinter", "error")
        all_ok = False
    
    # minecraft_launcher_lib
    try:
        import minecraft_launcher_lib
        ver = getattr(minecraft_launcher_lib, "__version__", "?")
        log(f"minecraft-launcher-lib {ver}", "ok")
    except ImportError:
        log("minecraft-launcher-lib not found! Install: pip install minecraft-launcher-lib", "error")
        all_ok = False
    
    # Inno Setup (Windows only)
    if IS_WINDOWS:
        inno = shutil.which("iscc")
        if inno:
            log(f"Inno Setup Compiler at {inno}", "ok")
        else:
            log("Inno Setup not found. Install from https://jrsoftware.org/isdl.php", "warn")
            log("Installer creation will be skipped.", "warn")
    
    # NSIS (alternative on Windows)
    if IS_WINDOWS:
        nsis = shutil.which("makensis")
        if nsis:
            log(f"NSIS at {nsis}", "ok")
    
    # Create build directories
    DIST.mkdir(parents=True, exist_ok=True)
    (BUILD / "temp").mkdir(parents=True, exist_ok=True)
    
    return all_ok


def step_build_exe() -> Path:
    """
    Build the executable using PyInstaller.
    Returns the path to the output directory.
    """
    print(f"\n{Colored.header('═' * 60)}")
    print(f"{Colored.header('  Building Executable')}")
    print(f"{Colored.header('═' * 60)}")
    
    pi = find_pyinstaller()
    if not pi:
        raise RuntimeError("PyInstaller not found")
    
    ctk_path = find_customtkinter()
    if not ctk_path:
        raise RuntimeError("customtkinter not found")
    
    version = get_version()
    log(f"Version: {version}", "info")
    
    # Determine platform
    if IS_WINDOWS:
        plat = "windows"
    elif IS_MACOS:
        plat = "darwin"
    else:
        plat = "linux"
    
    # Build command
    opts = list(PYINSTALLER_OPTS[plat])
    
    # Add customtkinter data files
    add_data = f"{ctk_path};customtkinter/" if IS_WINDOWS else f"{ctk_path}:customtkinter/"
    opts.extend(["--add-data", add_data])
    
    # Add the source file
    source = SRC / "ultrawater.py"
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    
    opts.append(str(source))
    
    # Clean previous build
    dist_dir = ROOT / "dist" / APP_NAME
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if (ROOT / "build" / APP_NAME).exists():
        shutil.rmtree(ROOT / "build" / APP_NAME)
    
    # Run PyInstaller
    cmd = [pi] + opts
    run(cmd)
    
    # Verify output
    exe_path = dist_dir
    if not exe_path.exists():
        raise RuntimeError(f"Build output not found at {exe_path}")
    
    # Count files
    file_count = len(list(exe_path.rglob("*")))
    total_size = sum(f.stat().st_size for f in exe_path.rglob("*") if f.is_file())
    
    log(f"Executable built at: {exe_path}", "ok")
    log(f"Files: {file_count}, Size: {total_size / 1024 / 1024:.1f} MB", "ok")
    
    return exe_path


def step_create_archive(exe_dir: Path) -> Path:
    """
    Create a compressed archive of the build.
    Returns path to the archive.
    """
    print(f"\n{Colored.header('═' * 60)}")
    print(f"{Colored.header('  Creating Archive')}")
    print(f"{Colored.header('═' * 60)}")
    
    version = get_version()
    platform_tag = f"{platform.system().lower()}-{ARCH.lower()}"
    archive_name = f"{APP_NAME.lower()}-{version}-{platform_tag}"
    
    if IS_WINDOWS:
        archive_path = DIST / f"{archive_name}.zip"
        log(f"Creating ZIP archive: {archive_path.name}")
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in exe_dir.rglob("*"):
                arcname = str(file_path.relative_to(exe_dir.parent))
                zf.write(file_path, arcname)
    else:
        archive_path = DIST / f"{archive_name}.tar.gz"
        log(f"Creating tar.gz archive: {archive_path.name}")
        with tarfile.open(archive_path, 'w:gz') as tf:
            tf.add(exe_dir, arcname=exe_dir.name)
    
    size_mb = archive_path.stat().st_size / 1024 / 1024
    log(f"Archive created: {archive_path} ({size_mb:.1f} MB)", "ok")
    
    # Create latest symlink/copy
    latest = DIST / f"{APP_NAME.lower()}-latest-{platform.system().lower()}.zip"
    if IS_WINDOWS:
        shutil.copy2(archive_path, latest)
    else:
        if latest.exists():
            latest.unlink()
        latest.hardlink_to(archive_path) if hasattr(Path, 'hardlink_to') else shutil.copy2(archive_path, latest)
    
    return archive_path


def step_create_installer(exe_dir: Path) -> Optional[Path]:
    """
    Create a platform-specific installer.
    Windows: Inno Setup .exe
    macOS: .dmg
    Linux: .deb or .AppImage via simple script
    """
    print(f"\n{Colored.header('═' * 60)}")
    print(f"{Colored.header('  Creating Installer')}")
    print(f"{Colored.header('═' * 60)}")
    
    version = get_version()
    
    if IS_WINDOWS:
        return _create_windows_installer(exe_dir, version)
    elif IS_MACOS:
        return _create_macos_dmg(exe_dir, version)
    else:
        return _create_linux_package(exe_dir, version)


def _create_windows_installer(exe_dir: Path, version: str) -> Optional[Path]:
    """Create a Windows installer using Inno Setup."""
    iscc = shutil.which("iscc")
    if not iscc:
        log("Inno Setup not found, skipping installer creation", "warn")
        return None
    
    # Generate Inno Setup script
    iss_path = BUILD / "UltraWater_installer.iss"
    guid = _generate_guid()
    
    script = f"""
#define MyAppName "UltraWater Client"
#define MyAppVersion "{version}"
#define MyAppPublisher "UltraWater"
#define MyAppURL "https://ultrawater.gg"
#define MyAppExeName "UltraWater.exe"
#define MyAppAssocName "UltraWater Profile"
#define MyAppAssocExt ".uwprofile"

[Setup]
AppId={{{guid}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
AppSupportURL={{#MyAppURL}}
AppUpdatesURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={DIST.as_posix()}
OutputBaseFilename=UltraWater-{version}-Setup
SetupIconFile={str(ASSETS / 'icon.ico').replace(os.sep, '/')}
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked

[Files]
Source: "{exe_dir.as_posix()}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{{userappdata}}\\.ultrawater"; Flags: uninsalwaysuninstall

[Icons]
Name: "{{autoprograms}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#MyAppName}}}}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\\Classes\\.uwprofile"; ValueType: string; ValueName: ""; ValueData: "UltraWaterProfile"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\\Classes\\UltraWaterProfile"; ValueType: string; ValueName: ""; ValueData: "UltraWater Profile"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\\Classes\\UltraWaterProfile\\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{{app}}\\{{#MyAppExeName}},1"
Root: HKCU; Subkey: "Software\\Classes\\UltraWaterProfile\\shell\\open\\command"; ValueType: string; ValueName: ""; ValueData: '"{{app}}\\{{#MyAppExeName}}" "%1"'

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;
"""
    
    iss_path.write_text(textwrap.dedent(script).strip())
    log(f"Inno Setup script written to {iss_path}", "ok")
    
    # Compile
    result = run([iscc, str(iss_path)])
    
    # Find output
    installer_name = f"UltraWater-{version}-Setup.exe"
    installer_path = DIST / installer_name
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / 1024 / 1024
        log(f"Installer created: {installer_path} ({size_mb:.1f} MB)", "ok")
        return installer_path
    else:
        # Try to find it
        for f in DIST.glob("UltraWater-*-Setup.exe"):
            size_mb = f.stat().st_size / 1024 / 1024
            log(f"Installer created: {f} ({size_mb:.1f} MB)", "ok")
            return f
        log("Installer not found after compilation", "error")
        return None


def _create_macos_dmg(exe_dir: Path, version: str) -> Optional[Path]:
    """Create a macOS DMG."""
    # Requires create-dmg or genisoimage
    dmg_path = DIST / f"UltraWater-{version}.dmg"
    
    # Try using create-dmg if available
    create_dmg = shutil.which("create-dmg")
    if create_dmg:
        log("Using create-dmg...")
        run([
            create_dmg,
            "--volname", f"UltraWater {version}",
            "--window-pos", "200", "120",
            "--window-size", "600", "400",
            "--icon-size", "100",
            "--icon", f"{APP_NAME}.app", "175", "120",
            "--hide-extension", f"{APP_NAME}.app",
            "--app-drop-link", "425", "120",
            str(dmg_path),
            str(exe_dir),
        ])
        return dmg_path
    
    # Fallback: use genisoimage
    geniso = shutil.which("genisoimage") or shutil.which("mkisofs")
    if geniso:
        log("Using genisoimage...")
        run([
            geniso,
            "-V", f"UltraWater {version}",
            "-D", "-R", "-apple",
            "-o", str(dmg_path),
            str(exe_dir),
        ])
        return dmg_path
    
    log("No DMG creation tool found (install create-dmg or genisoimage)", "warn")
    return None


def _create_linux_package(exe_dir: Path, version: str) -> Optional[Path]:
    """Create a Linux AppImage-style package."""
    appimage_dir = DIST / f"UltraWater-{version}-linux-{ARCH}"
    if appimage_dir.exists():
        shutil.rmtree(appimage_dir)
    
    # Just copy the build directory with a proper name
    shutil.copytree(exe_dir, appimage_dir)
    
    # Create a .desktop file
    desktop = f"""
[Desktop Entry]
Name=UltraWater Client
Comment=Ultralight Minecraft Launcher
Exec={appimage_dir.name}/UltraWater
Icon=ultrawater
Terminal=false
Type=Application
Categories=Game;Utility;
StartupWMClass=UltraWater
"""
    desktop_path = appimage_dir.parent / f"UltraWater-{version}.desktop"
    desktop_path.write_text(textwrap.dedent(desktop).strip())
    
    log(f"Linux package prepared at {appimage_dir}", "ok")
    
    # Create tar.gz of the build
    archive = DIST / f"UltraWater-{version}-linux-{ARCH}.tar.gz"
    with tarfile.open(archive, 'w:gz') as tf:
        tf.add(appimage_dir, arcname=appimage_dir.name)
        tf.add(desktop_path, arcname=desktop_path.name)
    
    log(f"Linux archive: {archive}", "ok")
    return archive


def _generate_guid() -> str:
    """Generate a deterministic GUID based on the app name."""
    import hashlib
    hash_obj = hashlib.md5("UltraWater Client".encode())
    hex_digest = hash_obj.hexdigest()
    return f"{hex_digest[:8]}-{hex_digest[8:12]}-{hex_digest[12:16]}-{hex_digest[16:20]}-{hex_digest[20:32]}"


def step_generate_checksums() -> Path:
    """Generate SHA256 checksums for all distribution files."""
    print(f"\n{Colored.header('═' * 60)}")
    print(f"{Colored.header('  Generating Checksums')}")
    print(f"{Colored.header('═' * 60)}")
    
    checksum_path = DIST / "checksums.sha256"
    lines = []
    
    for f in sorted(DIST.iterdir()):
        if f.is_file() and f.suffix in ('.zip', '.gz', '.exe', '.dmg', '.AppImage'):
            sha = hashlib.sha256()
            with open(f, 'rb') as fp:
                for chunk in iter(lambda: fp.read(8192), b''):
                    sha.update(chunk)
            lines.append(f"{sha.hexdigest()}  {f.name}")
            log(f"{f.name}: {sha.hexdigest()[:16]}...", "ok")
    
    checksum_path.write_text("\n".join(lines) + "\n")
    return checksum_path


def step_bump_version(bump_type: str = "patch"):
    """Bump the version number."""
    version = get_version()
    parts = [int(x) for x in version.split(".")]
    
    if bump_type == "major":
        parts = [parts[0] + 1, 0, 0]
    elif bump_type == "minor":
        parts = [parts[0], parts[1] + 1, 0]
    else:  # patch
        parts = [parts[0], parts[1], parts[2] + 1]
    
    new_version = ".".join(str(x) for x in parts)
    set_version(new_version)
    return new_version


def step_git_tag(version: str):
    """Create a git tag for the release."""
    if not shutil.which("git"):
        log("Git not available, skipping tag", "warn")
        return
    
    try:
        # Check if we're in a git repo
        run(["git", "rev-parse", "--git-dir"], capture=True)
        
        # Check for uncommitted changes
        result = run(["git", "status", "--porcelain"], capture=True)
        if result.stdout.strip():
            log("Uncommitted changes detected. Commit first or use --force.", "warn")
            return
        
        # Create tag
        tag = f"v{version}"
        run(["git", "tag", "-a", tag, "-m", f"Release {version}"])
        log(f"Tagged: {tag}", "ok")
        
    except subprocess.CalledProcessError:
        log("Not a git repository, skipping tag", "warn")


def step_clean():
    """Remove all build artifacts."""
    dirs_to_clean = [
        ROOT / "build" / APP_NAME,
        ROOT / "build" / "temp",
        ROOT / "dist" / APP_NAME,
        ROOT / "dist" / f"UltraWater-*",
    ]
    
    for d in dirs_to_clean:
        if isinstance(d, Path):
            paths = [d] if "*" not in str(d) else list(ROOT.glob(str(d.relative_to(ROOT))))
        else:
            paths = [d] if "*" not in str(d) else list(ROOT.glob(d))
        
        for p in paths:
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                log(f"Removed {p}", "ok")
    
    # Remove .spec files
    for spec in ROOT.glob("*.spec"):
        spec.unlink()
        log(f"Removed {spec}", "ok")
    
    # Remove pyinstaller temp
    for p in ROOT.glob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


# ── CLI ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="UltraWater Client Build & Release Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  all         Full build for current platform (exe + archive)
  exe         PyInstaller executable only
  archive     Create compressed archive from existing build
  installer   Build executable + platform installer (requires Inno Setup on Windows)
  release     Full release: bump version → build all → tag → checksums
  clean       Remove all build artifacts
  bump        Bump version number (--major, --minor, or --patch)
  checksums   Generate SHA256 checksums for distribution files
  check       Verify build environment only
        """
    )
    
    parser.add_argument("command", nargs="?", default="all",
                        help="Build command to execute")
    parser.add_argument("--major", action="store_true", help="Major version bump")
    parser.add_argument("--minor", action="store_true", help="Minor version bump")
    parser.add_argument("--patch", action="store_true", help="Patch version bump")
    parser.add_argument("--force", action="store_true", help="Force operations (skip warnings)")
    
    args = parser.parse_args()
    
    command = args.command
    
    if command == "clean":
        step_clean()
        return
    
    if command == "check":
        step_environment_check()
        return
    
    if command == "bump":
        bump = "patch"
        if args.major: bump = "major"
        elif args.minor: bump = "minor"
        new_ver = step_bump_version(bump)
        print(f"\n{Colored.ok(f'Version bumped to {new_ver}')}")
        return
    
    if command == "checksums":
        step_generate_checksums()
        return
    
    if command == "exe":
        step_environment_check()
        exe_dir = step_build_exe()
        log(f"Executable ready at {exe_dir}", "ok")
        return
    
    if command == "archive":
        exe_dir = ROOT / "dist" / APP_NAME
        if not exe_dir.exists():
            log(f"No build found at {exe_dir}. Run 'build.py exe' first.", "error")
            sys.exit(1)
        step_create_archive(exe_dir)
        return
    
    if command == "installer":
        step_environment_check()
        exe_dir = step_build_exe()
        installer = step_create_installer(exe_dir)
        if installer:
            log(f"Installer ready: {installer}", "ok")
        return
    
    if command == "release":
        bump = "patch"
        if args.major: bump = "major"
        elif args.minor: bump = "minor"
        
        new_ver = step_bump_version(bump)
        log(f"Building release v{new_ver}", "header")
        
        step_environment_check()
        exe_dir = step_build_exe()
        archive = step_create_archive(exe_dir)
        step_create_installer(exe_dir)
        step_generate_checksums()
        step_git_tag(new_ver)
        
        print(f"\n{Colored.ok('═' * 60)}")
        print(f"{Colored.ok(f'  Release v{new_ver} complete!')}")
        print(f"{Colored.ok('═' * 60)}")
        print(f"\nDistribution files in: {DIST}/")
        for f in sorted(DIST.iterdir()):
            if f.is_file() and f.name != "checksums.sha256":
                print(f"  {Colored.info(f.name)}")
        print(f"\nSHA256: {DIST / 'checksums.sha256'}")
        return
    
    # Default: "all"
    step_environment_check()
    exe_dir = step_build_exe()
    step_create_archive(exe_dir)
    step_create_installer(exe_dir)
    step_generate_checksums()
    
    print(f"\n{Colored.ok('═' * 60)}")
    print(f"{Colored.ok('  Build complete!')}")
    print(f"{Colored.ok('═' * 60)}")


if __name__ == "__main__":
    main()