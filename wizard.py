#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         UltraWater Client — Installation Wizard                             ║
║         v2.0.0                                                             ║
║                                                                             ║
║  A user-friendly first-run wizard that guides setup with:                   ║
║    •  Welcome screen with branding and feature highlights                   ║
║    •  Java detection — auto-find or browse to existing install              ║
║    •  Java download & install (Windows/macOS/Linux) via Adoptium API        ║
║    •  Minecraft directory selection with disk space check                   ║
║    •  Profile setup (username, RAM, performance options)                    ║
║    •  Summary with configuration review                                     ║
║                                                                             ║
║  Integration: Add to your launcher with:                                    ║
║      from wizard import run_setup_wizard                                     ║
║      if is_first_run():                                                      ║
║          run_setup_wizard()                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import hashlib
import urllib.request
import urllib.error
import io
import zipfile
import tarfile
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any, Tuple
from enum import Enum
from queue import Queue, Empty


# ══════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════

WIZARD_TITLE    = "UltraWater Client — Setup Wizard"
WIZARD_SIZE     = "760x620"
WIZARD_MIN_SIZE = (680, 560)

APP_NAME    = "UltraWater Client"
APP_DIR     = Path.home() / ".ultrawater"
MC_DIR      = Path.home() / ".minecraft"
CONFIG_FILE = APP_DIR / "config.json"
PROFILES_FILE = APP_DIR / "profiles.json"

# Adoptium API for Java downloads
ADOPTIUM_API = "https://api.adoptium.net/v3"

# Color palette (matches the launcher)
class C:
    BG0 = "#020b18"
    BG1 = "#041c30"
    BG2 = "#072d4a"
    BG3 = "#0d3d5c"
    ACC = "#12c8ff"
    AC2 = "#0a9fd4"
    AC3 = "#064d6e"
    TXT = "#e8f6ff"
    MUT = "#7ab8d4"
    GRN = "#39ff7a"
    GLD = "#f0b030"
    RED = "#ff5050"

FONT_TITLE  = ("Consolas", 22, "bold")
FONT_HEAD   = ("Consolas", 14, "bold")
FONT_BODY   = ("Consolas", 12)
FONT_SMALL  = ("Consolas", 10)
FONT_MONO   = ("Courier New", 11)

STEPS = [
    "Welcome",
    "Java Runtime",
    "Game Directory",
    "Your Profile",
    "Ready!",
]

POPULAR_RAM = [1024, 2048, 3072, 4096, 6144, 8192, 12288, 16384]


# ══════════════════════════════════════════════════════════
#  Data Model
# ══════════════════════════════════════════════════════════

@dataclass
class SetupState:
    """Tracks the user's choices through the wizard."""
    username: str = "UltraPlayer"
    memory_mb: int = 4096
    java_path: str = ""
    java_auto_detected: bool = True
    java_downloaded: bool = False
    game_dir: str = str(MC_DIR)
    version: str = "26.1.2"
    loader: str = "vanilla"
    fps_optimize: bool = True
    close_on_launch: bool = False
    show_snapshots: bool = False
    completed: bool = False


# ══════════════════════════════════════════════════════════
#  Java Detection & Download Utilities
# ══════════════════════════════════════════════════════════

def find_java() -> Optional[str]:
    """Find a suitable Java 25+ executable."""
    candidates = _get_java_candidates()
    
    for java in candidates:
        if java and Path(java).exists():
            version = _get_java_version(str(java))
            if version and version >= 25:
                return str(java)
    
    # Try PATH
    java_cmd = "java.exe" if platform.system() == "Windows" else "java"
    found = shutil.which(java_cmd)
    if found:
        version = _get_java_version(found)
        if version and version >= 25:
            return found
    
    return None


def _get_java_candidates() -> List[str]:
    """Return a list of likely Java paths for the current platform."""
    system = platform.system()
    candidates = []
    
    if system == "Windows":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        
        for base in [program_files, program_files_x86]:
            for vendor_dir in Path(base).iterdir():
                if "java" in vendor_dir.name.lower() or "jdk" in vendor_dir.name.lower() or "jre" in vendor_dir.name.lower() or "temurin" in vendor_dir.name.lower() or "adopt" in vendor_dir.name.lower() or "corretto" in vendor_dir.name.lower() or "bellsoft" in vendor_dir.name.lower() or "zulu" in vendor_dir.name.lower():
                    java_exe = vendor_dir / "bin" / "java.exe"
                    if java_exe.exists():
                        candidates.append(str(java_exe))
                    # Also check subdirectories
                    for sub in vendor_dir.iterdir():
                        if sub.is_dir():
                            je = sub / "bin" / "java.exe"
                            if je.exists():
                                candidates.append(str(je))
        
        # JAVA_HOME
        jh = os.environ.get("JAVA_HOME", "")
        if jh:
            candidates.append(str(Path(jh) / "bin" / "java.exe"))
        
    elif system == "Darwin":
        candidates.extend([
            "/usr/bin/java",
            "/Library/Java/JavaVirtualMachines/temurin-25.jdk/Contents/Home/bin/java",
            "/Library/Java/JavaVirtualMachines/jdk-25.jdk/Contents/Home/bin/java",
            "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/bin/java",
        ])
        # java_home utility
        try:
            result = subprocess.run(
                ["/usr/libexec/java_home", "--version", "25"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                jh_path = result.stdout.strip()
                candidates.append(str(Path(jh_path) / "bin" / "java"))
        except subprocess.SubprocessError:
            pass
        # Homebrew
        for base in ["/opt/homebrew", "/usr/local", "/opt/local"]:
            for d in ["", "/Cellar"]:
                for sub in ["openjdk", "openjdk@25", "temurin25"]:
                    p = Path(f"{base}{d}/{sub}/bin/java")
                    if p.exists():
                        candidates.append(str(p))
    else:  # Linux
        candidates.extend([
            "/usr/bin/java",
            "/usr/lib/jvm/java-25-openjdk-amd64/bin/java",
            "/usr/lib/jvm/java-25-openjdk-arm64/bin/java",
            "/usr/lib/jvm/java-25-openjdk/bin/java",
            "/usr/lib/jvm/default-java/bin/java",
            "/usr/local/opt/openjdk/bin/java",
            "/usr/local/opt/openjdk@25/bin/java",
        ])
        # update-alternatives
        try:
            result = subprocess.run(
                ["update-alternatives", "--list", "java"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    candidates.append(line.strip())
        except subprocess.SubprocessError:
            pass
        jh = os.environ.get("JAVA_HOME", "")
        if jh:
            candidates.append(str(Path(jh) / "bin" / "java"))
    
    return [c for c in candidates if c]


def _get_java_version(java_path: str) -> Optional[int]:
    """Get the major version number from a Java executable."""
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout + result.stderr
        
        for pattern in [
            r'(?:version\s+")?(?:1\.)?(\d+)',
            r'openjdk\s+version\s+"(\d+)',
            r'version\s+"(\d+)',
        ]:
            match = re.search(pattern, output)
            if match:
                return int(match.group(1))
        
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        pass
    
    return None


def get_java_info(java_path: str) -> Dict[str, str]:
    """Get detailed Java information."""
    info = {
        "path": java_path,
        "version": "Unknown",
        "vendor": "Unknown",
        "arch": "Unknown",
        "valid": False,
        "major": 0,
    }
    
    if not java_path or not Path(java_path).exists():
        info["path"] = "Not found"
        return info
    
    try:
        result = subprocess.run(
            [java_path, "-XshowSettings:properties", "-version"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        
        ver_match = re.search(r'java\s+(?:runtime\s+)?version\s+"([^"]+)"', output, re.IGNORECASE)
        if ver_match:
            info["version"] = ver_match.group(1)
        
        vendor_match = re.search(r'java\.vendor\s*=\s*(\S.+)', output)
        if vendor_match:
            info["vendor"] = vendor_match.group(1).strip()
        
        arch_match = re.search(r'os\.arch\s*=\s*(\S+)', output)
        if arch_match:
            info["arch"] = arch_match.group(1)
        
        major = _get_java_version(java_path)
        info["major"] = major or 0
        info["valid"] = major is not None and major >= 25
        
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        pass
    
    return info


# ══════════════════════════════════════════════════════════
#  Java Downloader
# ══════════════════════════════════════════════════════════

class JavaDownloader:
    """
    Downloads Eclipse Temurin (Adoptium) Java 25 for the current platform.
    Handles ZIP/tar.gz extraction and MSI/pkg installation.
    """
    
    FEATURE_VERSION = 25  # Updated to 25
    
    def __init__(self, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        self.progress_callback = progress_callback
        self._cancel = False
        self._system = platform.system()
        self._machine = self._normalize_arch(platform.machine())
    
    def _normalize_arch(self, arch: str) -> str:
        """Normalize architecture strings for Adoptium API."""
        arch = arch.lower()
        if arch in ("amd64", "x86_64", "x64"):
            return "x64"
        if arch in ("aarch64", "arm64"):
            return "arm64"
        if arch in ("x86", "i386", "i686"):
            return "x86"
        if "arm" in arch:
            return "arm"
        return arch
    
    def _get_os(self) -> str:
        """Get OS string for Adoptium API."""
        mapping = {
            "Windows": "windows",
            "Darwin": "mac",
            "Linux": "linux",
        }
        return mapping.get(self._system, "linux")
    
    def _get_image_type(self) -> str:
        """JRE for most users, JDK if we need javac."""
        return "jre"
    
    def _get_extension(self) -> str:
        """File extension for download."""
        if self._system == "Windows":
            return "msi"  # MSI installer for easy silent install
        elif self._system == "Darwin":
            return "pkg"
        else:
            return "tar.gz"
    
    def get_download_url(self) -> Optional[str]:
        """Get the download URL for the latest Java 25 JRE."""
        try:
            # Use the API to get the download link
            url = (
                f"{ADOPTIUM_API}/binary/latest/"
                f"{self.FEATURE_VERSION}/ga/"
                f"{self._get_os()}/{self._machine}/"
                f"{self._get_image_type()}/hotspot/normal/eclipse"
            )
            
            self._report_progress(0, 0, "Fetching download link...")
            
            # We need to follow redirects to get the actual filename
            req = urllib.request.Request(url, method="HEAD")
            # Add a user-agent
            req.add_header("User-Agent", "UltraWaterClient/2.0.0")
            
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                response = urllib.request.urlopen(req, timeout=15, context=ctx)
            except Exception:
                # Fall back to regular request
                response = urllib.request.urlopen(req, timeout=15)
            
            final_url = response.geturl()
            
            self._report_progress(0, 0, f"Download URL: {final_url.split('/')[-1][:50]}...")
            return final_url
            
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            self._report_progress(0, 0, f"Failed to get download URL: {e}")
            return None
    
    def download_and_install(
        self,
        download_dir: Path,
        install_dir: Optional[Path] = None
    ) -> Optional[str]:
        """
        Download and install Java.
        Returns the path to the java executable, or None on failure.
        """
        self._cancel = False
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Get download URL
        url = self.get_download_url()
        if not url:
            return None
        
        filename = url.split("/")[-1].split("?")[0]
        if not filename.endswith((".msi", ".pkg", ".tar.gz", ".zip")):
            # Try to extract the filename from content-disposition
            filename = f"temurin-{self.FEATURE_VERSION}.{self._get_extension()}"
        
        filepath = download_dir / filename
        
        self._report_progress(0, 0, f"Downloading {filename}...")
        
        # Download
        try:
            self._download_file(url, filepath)
        except Exception as e:
            self._report_progress(0, 0, f"Download failed: {e}")
            return None
        
        if self._cancel:
            filepath.unlink(missing_ok=True)
            return None
        
        self._report_progress(100, 100, "Download complete. Installing...")
        
        # Install
        java_path = self._install_java(filepath, install_dir)
        
        if java_path:
            self._report_progress(100, 100, f"Java installed at {java_path}")
        else:
            self._report_progress(0, 0, "Installation failed. You can install Java manually.")
        
        return java_path
    
    def _download_file(self, url: str, dest: Path) -> None:
        """Download a file with progress reporting."""
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "UltraWaterClient/2.0.0")
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            response = urllib.request.urlopen(req, timeout=60, context=ctx)
        except Exception:
            response = urllib.request.urlopen(req, timeout=60)
        
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 8192
        
        with open(dest, "wb") as f:
            while True:
                if self._cancel:
                    raise InterruptedError("Download cancelled")
                
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                
                if total_size > 0:
                    percent = int(downloaded * 100 / total_size)
                    mb_done = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    self._report_progress(
                        percent, 100,
                        f"Downloading... {mb_done:.1f}/{mb_total:.1f} MB ({percent}%)"
                    )
                else:
                    mb_done = downloaded / (1024 * 1024)
                    self._report_progress(0, 0, f"Downloading... {mb_done:.1f} MB")
    
    def _install_java(self, filepath: Path, install_dir: Optional[Path] = None) -> Optional[str]:
        """Install the downloaded Java package."""
        system = self._system
        
        if system == "Windows":
            return self._install_windows(filepath)
        elif system == "Darwin":
            return self._install_macos(filepath)
        else:
            return self._install_linux(filepath, install_dir)
    
    def _install_windows(self, filepath: Path) -> Optional[str]:
        """Install JRE via MSI silently."""
        if filepath.suffix == ".msi":
            self._report_progress(0, 0, "Running MSI installer silently...")
            try:
                # Silent install with environment variables set
                subprocess.run(
                    [
                        "msiexec.exe", "/i", str(filepath),
                        "/quiet", "/norestart",
                        "ADDLOCAL=FeatureMain,FeatureEnvironment,FeatureJarFileRunWith,FeatureJavaHome",
                        "INSTALLDIR=C:\\Program Files\\Temurin\\",
                    ],
                    check=True, timeout=300, capture_output=True
                )
                
                # Find the installed Java
                java_path = find_java()
                if java_path:
                    filepath.unlink(missing_ok=True)  # Clean up installer
                    return java_path
                
                # Check default install location
                for base in ["C:\\Program Files\\Temurin", "C:\\Program Files\\Eclipse Adoptium"]:
                    for sub in Path(base).iterdir():
                        je = sub / "bin" / "java.exe"
                        if je.exists():
                            filepath.unlink(missing_ok=True)
                            return str(je)
                
            except subprocess.TimeoutExpired:
                self._report_progress(0, 0, "MSI installer timed out", "WARN")
            except subprocess.CalledProcessError as e:
                self._report_progress(0, 0, f"MSI installer failed: {e}", "WARN")
        
        elif filepath.suffix == ".zip":
            # Portable zip — extract to a known location
            dest = APP_DIR / "java" / "temurin-25"
            dest.mkdir(parents=True, exist_ok=True)
            
            self._report_progress(0, 0, "Extracting zip...")
            with zipfile.ZipFile(filepath, "r") as zf:
                zf.extractall(dest)
            
            # Find java.exe in the extracted dir
            for j in dest.rglob("java.exe"):
                filepath.unlink(missing_ok=True)
                return str(j)
        
        return None
    
    def _install_macos(self, filepath: Path) -> Optional[str]:
        """Install JRE via PKG on macOS."""
        self._report_progress(0, 0, "Running PKG installer (may need password)...")
        try:
            subprocess.run(
                ["sudo", "installer", "-pkg", str(filepath), "-target", "/"],
                check=True, timeout=300, capture_output=True
            )
            
            # Find installed Java
            java_path = find_java()
            if java_path:
                filepath.unlink(missing_ok=True)
                return java_path
            
            # Check standard locations
            for p in [
                "/Library/Java/JavaVirtualMachines/temurin-25.jdk/Contents/Home/bin/java",
                "/Library/Java/JavaVirtualMachines/jdk-25.jdk/Contents/Home/bin/java",
            ]:
                if Path(p).exists():
                    return p
            
        except subprocess.CalledProcessError as e:
            self._report_progress(0, 0, f"PKG installer failed: {e}", "WARN")
        except subprocess.TimeoutExpired:
            self._report_progress(0, 0, "PKG installer timed out", "WARN")
        
        return None
    
    def _install_linux(self, filepath: Path, install_dir: Optional[Path] = None) -> Optional[str]:
        """Extract tar.gz to a known location on Linux."""
        dest = install_dir or (APP_DIR / "java" / "temurin-25")
        dest.mkdir(parents=True, exist_ok=True)
        
        self._report_progress(0, 0, "Extracting archive...")
        
        # tar.gz
        if filepath.suffix == ".gz" or str(filepath).endswith(".tar.gz"):
            import tarfile
            try:
                with tarfile.open(filepath, "r:gz") as tf:
                    # Find the top-level directory
                    members = tf.getmembers()
                    top_dirs = set(m.split("/")[0] for m in members if "/" in m)
                    
                    if top_dirs:
                        # Extract to temp then move
                        temp_dir = dest.parent / f".temp_extract_{int(time.time())}"
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        tf.extractall(temp_dir)
                        
                        # Move contents to final destination
                        for td in top_dirs:
                            src = temp_dir / td
                            if src.exists():
                                for item in src.iterdir():
                                    dst = dest / item.name
                                    if dst.exists():
                                        shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
                                    shutil.move(str(item), str(dst))
                        
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    else:
                        tf.extractall(dest)
                
                # Find java
                for j in dest.rglob("java"):
                    if "bin" in str(j):
                        filepath.unlink(missing_ok=True)
                        return str(j)
                
            except (tarfile.TarError, OSError, IOError) as e:
                self._report_progress(0, 0, f"Extraction failed: {e}", "WARN")
        
        return None
    
    def _report_progress(self, current: int, total: int, status: str, level: str = "INFO") -> None:
        if self.progress_callback:
            self.progress_callback(current, total, status)
    
    def cancel(self) -> None:
        self._cancel = True


# ══════════════════════════════════════════════════════════
#  Wizard Page — Base Class
# ══════════════════════════════════════════════════════════

class WizardPage(ctk.CTkFrame):
    """Base class for wizard step pages."""
    
    def __init__(self, master: "InstallWizard", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.wizard = master
    
    def on_enter(self) -> None:
        """Called when this page becomes visible."""
        pass
    
    def on_exit(self) -> bool:
        """Called before leaving. Return False to block."""
        return True
    
    def on_finish(self) -> bool:
        """Called when wizard completes. Return False to abort."""
        return True


# ══════════════════════════════════════════════════════════
#  Step 1: Welcome Page
# ══════════════════════════════════════════════════════════

class WelcomePage(WizardPage):
    """Welcome screen with branding and quick intro."""
    
    def on_enter(self):
        for w in self.winfo_children():
            w.destroy()
        
        # Center content
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.45, anchor="center")
        
        # Water drop logo
        drop = ctk.CTkFrame(container, fg_color=C.ACC, corner_radius=50, width=80, height=80)
        drop.pack(pady=(0, 20))
        drop.pack_propagate(False)
        ctk.CTkLabel(
            drop, text="UW",
            font=("Consolas", 30, "bold"),
            text_color=C.BG0
        ).pack(expand=True)
        
        # Title
        ctk.CTkLabel(
            container, text="UltraWater Client",
            font=("Consolas", 32, "bold"),
            text_color=C.TXT
        ).pack()
        
        ctk.CTkLabel(
            container, text="Ultralight Minecraft Launcher",
            font=("Consolas", 15),
            text_color=C.ACC
        ).pack(pady=(4, 24))
        
        # Feature pills in a flow layout
        features = [
            ("⚡  No Ads — Forever", C.GRN),
            ("🎮  500+ Versions", C.ACC),
            ("📦  Built-in Mod Manager", C.GLD),
            ("🎨  Beautiful Dark Theme", C.ACC),
            ("🐍  100% Open Source", C.GRN),
        ]
        
        pills_frame = ctk.CTkFrame(container, fg_color="transparent")
        pills_frame.pack()
        
        for i, (text, color) in enumerate(features):
            pill = ctk.CTkFrame(pills_frame, fg_color=C.BG2, corner_radius=16)
            pill.pack(pady=3)
            ctk.CTkLabel(
                pill, text=text,
                font=("Consolas", 12),
                text_color=color
            ).pack(padx=18, pady=6)
        
        # Footer text
        ctk.CTkLabel(
            container,
            text="This quick wizard will get you set up in under a minute.",
            font=FONT_SMALL,
            text_color=C.MUT
        ).pack(pady=(24, 0))
        
        # Allow proceeding from the welcome page
        self.wizard.can_proceed = True
        self.wizard._update_nav()


# ══════════════════════════════════════════════════════════
#  Step 2: Java Detection & Download Page
# ══════════════════════════════════════════════════════════

class JavaPage(WizardPage):
    """
    Java runtime setup:
    1. Auto-detect existing Java 25+
    2. If not found: offer download + install or manual browse
    3. Show detailed Java info when detected
    """
    
    def __init__(self, master: "InstallWizard", **kwargs):
        super().__init__(master, **kwargs)
        self._detection_lock = threading.Lock()
        self._downloader: Optional[JavaDownloader] = None
    
    def on_enter(self):
        for w in self.winfo_children():
            w.destroy()
        
        # ── Header ──
        ctk.CTkLabel(
            self, text="☕  Java Runtime",
            font=FONT_TITLE, text_color=C.TXT
        ).pack(padx=40, pady=(28, 4), anchor="w")
        
        ctk.CTkLabel(
            self, text="Minecraft requires Java 25 or newer to run.",
            font=FONT_BODY, text_color=C.MUT
        ).pack(padx=40, anchor="w")
        
        # ── Status card ──
        self._status_card = ctk.CTkFrame(self, fg_color=C.BG1, corner_radius=12)
        self._status_card.pack(fill="x", padx=40, pady=16)
        
        # Icon + status row
        status_row = ctk.CTkFrame(self._status_card, fg_color="transparent")
        status_row.pack(pady=(20, 0))
        
        self._status_icon = ctk.CTkLabel(
            status_row, text="⟳",
            font=("Consolas", 28), text_color=C.MUT
        )
        self._status_icon.pack(side="left", padx=(0, 12))
        
        self._status_title = ctk.CTkLabel(
            status_row, text="Checking for Java...",
            font=FONT_HEAD, text_color=C.TXT
        )
        self._status_title.pack(side="left")
        
        self._status_detail = ctk.CTkLabel(
            self._status_card, text="Scanning your system...",
            font=FONT_SMALL, text_color=C.MUT, wraplength=550
        )
        self._status_detail.pack(pady=(8, 20))
        
        # ── Action buttons ──
        self._action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._action_frame.pack(fill="x", padx=40, pady=8)
        
        # Progress bar (hidden initially)
        self._progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._progress_frame.pack(fill="x", padx=40, pady=8)
        
        self._progress_bar = ctk.CTkProgressBar(
            self._progress_frame, fg_color=C.BG2, progress_color=C.ACC,
            height=6, corner_radius=3, mode="determinate"
        )
        self._progress_bar.set(0)
        self._progress_label = ctk.CTkLabel(
            self._progress_frame, text="", font=FONT_SMALL, text_color=C.MUT
        )
        # Don't pack yet — only show during download
        
        # ── Auto-detect ──
        self.after(400, self._start_detection)
    
    def _start_detection(self):
        with self._detection_lock:
            self._status_icon.configure(text="⟳", text_color=C.MUT)
            self._status_title.configure(text="Searching for Java 25+...")
            self._status_detail.configure(text="Checking common install locations and PATH...")
        
        def detect():
            java_path = find_java()
            self.after(0, lambda: self._on_detection_result(java_path))
        
        threading.Thread(target=detect, daemon=True).start()
    
    def _on_detection_result(self, java_path: Optional[str]):
        # Clear any download widgets
        self._progress_bar.pack_forget()
        self._progress_label.pack_forget()
        
        self.wizard.can_proceed = False  # Will be set true if we have Java or user chooses to skip
        
        # Clear action frame
        for w in self._action_frame.winfo_children():
            w.destroy()
        
        if java_path:
            info = get_java_info(java_path)
            
            self._status_icon.configure(text="✓", text_color=C.GRN)
            self._status_title.configure(
                text=f"Java {info['version']} Found!",
                text_color=C.GRN
            )
            self._status_detail.configure(
                text=f"{info['vendor']}  •  {info['arch']}\n"
                     f"📂  {java_path}",
                text_color=C.MUT
            )
            
            self.wizard.setup_state.java_path = java_path
            self.wizard.setup_state.java_auto_detected = True
            self.wizard.setup_state.java_downloaded = False
            self.wizard.can_proceed = True
            
            # Show "Looks good!" button
            ctk.CTkButton(
                self._action_frame,
                text="✓  Looks good! Continue →",
                command=lambda: self.wizard._next_step(),
                fg_color=C.GRN, hover_color="#2cdd64",
                text_color=C.BG0, font=FONT_HEAD,
                corner_radius=8, height=40, width=260
            ).pack(pady=8)
        
        else:
            self._status_icon.configure(text="✗", text_color=C.RED)
            self._status_title.configure(
                text="Java 25+ Not Found",
                text_color=C.RED
            )
            self._status_detail.configure(
                text="Don't worry — we can help you get it set up.",
                text_color=C.MUT
            )
            
            self.wizard.setup_state.java_path = ""
            self.wizard.setup_state.java_auto_detected = False
            
            # Option 1: Download Java
            ctk.CTkButton(
                self._action_frame,
                text="⬇  Download Java 25 (Recommended)",
                command=self._download_and_install_java,
                fg_color=C.ACC, hover_color=C.AC2,
                text_color=C.BG0, font=FONT_HEAD,
                corner_radius=8, height=42, width=320
            ).pack(pady=4)
            
            # Option 2: Browse
            ctk.CTkButton(
                self._action_frame,
                text="📁  I already have Java — Browse for it",
                command=self._browse_for_java,
                fg_color=C.BG2, hover_color=C.BG3,
                text_color=C.TXT, font=FONT_BODY,
                border_color=C.AC3, border_width=1,
                corner_radius=8, height=34, width=320
            ).pack(pady=4)
            
            # Option 3: Skip
            ctk.CTkButton(
                self._action_frame,
                text="⏭  Skip for now (I'll set it up later)",
                command=self._skip_java,
                fg_color="transparent",
                text_color=C.MUT, font=FONT_SMALL,
                hover=False, corner_radius=8, height=28, width=260
            ).pack(pady=4)
        
        self.wizard._update_nav()
    
    def _download_and_install_java(self):
        """Download and install Java 25."""
        self._status_icon.configure(text="⬇", text_color=C.GLD)
        self._status_title.configure(text="Downloading Java 25...", text_color=C.GLD)
        self._status_detail.configure(text="Preparing download...")
        
        # Show progress bar
        self._progress_bar.pack(fill="x", pady=(8, 4))
        self._progress_label.pack()
        self._progress_bar.set(0)
        
        # Disable action buttons
        for w in self._action_frame.winfo_children():
            w.configure(state="disabled") if hasattr(w, 'configure') else None
        
        # Cancel button
        self._cancel_btn = ctk.CTkButton(
            self._action_frame,
            text="✗  Cancel Download",
            command=self._cancel_download,
            fg_color=C.BG2, hover_color=C.BG3,
            text_color=C.RED, font=FONT_SMALL,
            border_color=C.AC3, border_width=1,
            corner_radius=6, height=28, width=160
        )
        self._cancel_btn.pack(pady=4)
        
        self.wizard.can_proceed = False
        self.wizard._update_nav()
        
        # Start download in background
        def download_thread():
            self._downloader = JavaDownloader(progress_callback=self._update_progress)
            java_path = self._downloader.download_and_install(
                download_dir=APP_DIR / "downloads",
                install_dir=APP_DIR / "java" / "temurin-25"
            )
            self.after(0, lambda: self._on_download_complete(java_path))
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def _update_progress(self, current: int, total: int, status: str):
        """Update progress bar from download thread."""
        if total > 0:
            self._progress_bar.configure(mode="determinate")
            self._progress_bar.set(current / total)
        else:
            self._progress_bar.configure(mode="indeterminate")
            self._progress_bar.start()
        
        self._progress_label.configure(text=status)
    
    def _on_download_complete(self, java_path: Optional[str]):
        self._progress_bar.stop() if self._progress_bar.cget("mode") == "indeterminate" else None
        
        for w in self._action_frame.winfo_children():
            w.destroy()
        
        if java_path:
            info = get_java_info(java_path)
            
            self._status_icon.configure(text="✓", text_color=C.GRN)
            self._status_title.configure(
                text=f"Java {info['version']} Installed!",
                text_color=C.GRN
            )
            self._status_detail.configure(
                text=f"Downloaded and installed successfully.\n"
                     f"📂  {java_path}",
                text_color=C.MUT
            )
            
            self.wizard.setup_state.java_path = java_path
            self.wizard.setup_state.java_downloaded = True
            self.wizard.can_proceed = True
            
            ctk.CTkButton(
                self._action_frame,
                text="✓  Continue →",
                command=lambda: self.wizard._next_step(),
                fg_color=C.GRN, hover_color="#2cdd64",
                text_color=C.BG0, font=FONT_HEAD,
                corner_radius=8, height=40, width=200
            ).pack(pady=8)
        else:
            self._status_icon.configure(text="✗", text_color=C.RED)
            self._status_title.configure(
                text="Installation Failed",
                text_color=C.RED
            )
            self._status_detail.configure(
                text="Could not download or install Java automatically.\n"
                     "Try browsing for an existing installation or installing manually.",
                text_color=C.MUT
            )
            
            # Retry
            ctk.CTkButton(
                self._action_frame,
                text="🔄  Retry Download",
                command=self._download_and_install_java,
                fg_color=C.ACC, hover_color=C.AC2,
                text_color=C.BG0, font=FONT_HEAD,
                corner_radius=8, height=38, width=240
            ).pack(pady=4)
            
            # Browse
            ctk.CTkButton(
                self._action_frame,
                text="📁  Browse for Java",
                command=self._browse_for_java,
                fg_color=C.BG2, hover_color=C.BG3,
                text_color=C.TXT, font=FONT_BODY,
                border_color=C.AC3, border_width=1,
                corner_radius=8, height=34, width=240
            ).pack(pady=4)
            
            # Skip
            ctk.CTkButton(
                self._action_frame,
                text="⏭  Skip",
                command=self._skip_java,
                fg_color="transparent",
                text_color=C.MUT, font=FONT_SMALL,
                hover=False, corner_radius=6, height=24, width=120
            ).pack(pady=4)
        
        self.wizard._update_nav()
    
    def _cancel_download(self):
        if self._downloader:
            self._downloader.cancel()
        self._status_title.configure(text="Cancelled", text_color=C.MUT)
        self._status_detail.configure(text="Download cancelled.")
        self._cancel_btn.configure(state="disabled")
    
    def _browse_for_java(self):
        """Let the user manually select a Java executable."""
        if platform.system() == "Windows":
            filetypes = [("Java executable", "java.exe"), ("All files", "*.*")]
        else:
            filetypes = [("Java executable", "java"), ("All files", "*")]
        
        path = filedialog.askopenfilename(
            title="Select Java executable",
            filetypes=filetypes
        )
        
        if path:
            java_path = str(Path(path).resolve())
            version = _get_java_version(java_path)
            
            if version and version >= 25:
                info = get_java_info(java_path)
                self._status_icon.configure(text="✓", text_color=C.GRN)
                self._status_title.configure(
                    text=f"Java {info['version']} Selected!",
                    text_color=C.GRN
                )
                self._status_detail.configure(
                    text=f"{info['vendor']}  •  {info['arch']}\n"
                         f"📂  {java_path}",
                    text_color=C.MUT
                )
                
                self.wizard.setup_state.java_path = java_path
                self.wizard.can_proceed = True
                
                for w in self._action_frame.winfo_children():
                    w.destroy()
                
                ctk.CTkButton(
                    self._action_frame,
                    text="✓  Looks good! Continue →",
                    command=lambda: self.wizard._next_step(),
                    fg_color=C.GRN, hover_color="#2cdd64",
                    text_color=C.BG0, font=FONT_HEAD,
                    corner_radius=8, height=40, width=260
                ).pack(pady=8)
            else:
                version_str = str(version) if version else "Unknown"
                self._status_detail.configure(
                    text=f"Selected Java version: {version_str}.\n"
                         f"Java 25+ is required. Please select a newer version.",
                    text_color=C.RED
                )
        
        self.wizard._update_nav()
    
    def _skip_java(self):
        self.wizard.setup_state.java_path = ""
        self.wizard.can_proceed = True  # Allow proceeding even without Java
        self.wizard._next_step()


# ══════════════════════════════════════════════════════════
#  Step 3: Game Directory Page
# ══════════════════════════════════════════════════════════

class DirectoryPage(WizardPage):
    """Choose where Minecraft lives / will be installed."""
    
    def __init__(self, master: "InstallWizard", **kwargs):
        super().__init__(master, **kwargs)
        self._dir_var = ctk.StringVar(value=str(MC_DIR))
    
    def on_enter(self):
        for w in self.winfo_children():
            w.destroy()
        
        ctk.CTkLabel(
            self, text="📂  Game Directory",
            font=FONT_TITLE, text_color=C.TXT
        ).pack(padx=40, pady=(28, 4), anchor="w")
        
        ctk.CTkLabel(
            self, text="Choose where Minecraft is (or will be) installed.",
            font=FONT_BODY, text_color=C.MUT
        ).pack(padx=40, anchor="w")
        
        # ── Directory card ──
        card = ctk.CTkFrame(self, fg_color=C.BG1, corner_radius=12)
        card.pack(fill="x", padx=40, pady=20)
        
        # Current directory display
        dir_display = ctk.CTkFrame(card, fg_color=C.BG2, corner_radius=8)
        dir_display.pack(fill="x", padx=20, pady=(20, 4))
        
        ctk.CTkLabel(
            dir_display, text="📍  Location:",
            font=FONT_SMALL, text_color=C.MUT
        ).pack(padx=12, pady=(8, 2), anchor="w")
        
        self._dir_label = ctk.CTkLabel(
            dir_display, text=str(MC_DIR),
            font=("Consolas", 13), text_color=C.ACC,
            wraplength=500, justify="left"
        )
        self._dir_label.pack(padx=12, pady=(0, 8), anchor="w")
        
        # Change button
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=(4, 20))
        
        ctk.CTkButton(
            btn_row,
            text="📁  Change Directory",
            command=self._browse_directory,
            fg_color=C.BG2, hover_color=C.BG3,
            text_color=C.TXT, font=FONT_BODY,
            border_color=C.AC3, border_width=1,
            corner_radius=8, height=36, width=200
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(
            btn_row,
            text="🔄  Use Default",
            command=self._use_default,
            fg_color=C.BG2, hover_color=C.BG3,
            text_color=C.TXT, font=FONT_BODY,
            border_color=C.AC3, border_width=1,
            corner_radius=8, height=36, width=160
        ).pack(side="left", padx=4)
        
        # ── Info section ──
        info_card = ctk.CTkFrame(self, fg_color=C.BG2, corner_radius=10)
        info_card.pack(fill="x", padx=40, pady=8)
        
        game_dir = Path(self._dir_var.get())
        
        # Disk space check
        try:
            if game_dir.exists():
                usage = shutil.disk_usage(game_dir)
                free_gb = usage.free / (1024**3)
                space_text = f"💾  Free disk space: {free_gb:.1f} GB  —  Plenty of room!"
                space_color = C.GRN if free_gb > 5 else C.GLD
            else:
                # Check parent
                parent = game_dir.parent
                if parent.exists():
                    usage = shutil.disk_usage(parent)
                    free_gb = usage.free / (1024**3)
                    space_text = f"💾  Free disk space: {free_gb:.1f} GB  —  Directory will be created"
                    space_color = C.GRN if free_gb > 5 else C.GLD
                else:
                    space_text = "💾  Could not check disk space"
                    space_color = C.MUT
        except (OSError, PermissionError):
            space_text = "💾  Could not check disk space"
            space_color = C.MUT
        
        ctk.CTkLabel(
            info_card, text=space_text,
            font=FONT_SMALL, text_color=space_color
        ).pack(padx=16, pady=12, anchor="w")
        
        # Existing installation check
        existing_mc = game_dir / "versions"
        if existing_mc.exists() and any(existing_mc.iterdir()):
            ctk.CTkLabel(
                info_card, text="✅  Existing Minecraft installation detected!",
                font=FONT_SMALL, text_color=C.GRN
            ).pack(padx=16, pady=(0, 12), anchor="w")
        
        # Directory page is always valid — user can always proceed
        self.wizard.can_proceed = True
        self.wizard._update_nav()
    
    def _browse_directory(self):
        path = filedialog.askdirectory(
            title="Select Minecraft Directory",
            mustexist=False
        )
        if path:
            self._dir_var.set(path)
            self._dir_label.configure(text=path)
            self.wizard.setup_state.game_dir = path
            # Refresh to update disk space info
            self.on_enter()
    
    def _use_default(self):
        self._dir_var.set(str(MC_DIR))
        self._dir_label.configure(text=str(MC_DIR))
        self.wizard.setup_state.game_dir = str(MC_DIR)
        self.on_enter()


# ══════════════════════════════════════════════════════════
#  Step 4: Profile Setup Page
# ══════════════════════════════════════════════════════════

class ProfilePage(WizardPage):
    """Configure username, RAM, and performance options."""
    
    def __init__(self, master: "InstallWizard", **kwargs):
        super().__init__(master, **kwargs)
        self._username_var = ctk.StringVar(value="UltraPlayer")
        self._ram_var = ctk.IntVar(value=4096)
        self._fps_var = ctk.BooleanVar(value=True)
        self._close_var = ctk.BooleanVar(value=False)
        self._snapshots_var = ctk.BooleanVar(value=False)
    
    def on_enter(self):
        for w in self.winfo_children():
            w.destroy()
        
        # ── Header ──
        ctk.CTkLabel(
            self, text="👤  Your Profile",
            font=FONT_TITLE, text_color=C.TXT
        ).pack(padx=40, pady=(28, 4), anchor="w")
        
        ctk.CTkLabel(
            self, text="Set up your player preferences.",
            font=FONT_BODY, text_color=C.MUT
        ).pack(padx=40, anchor="w")
        
        # ── Scrollable form ──
        form = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=C.AC3,
            scrollbar_button_hover_color=C.ACC
        )
        form.pack(fill="both", expand=True, padx=40, pady=12)
        
        # ── Username ──
        username_card = ctk.CTkFrame(form, fg_color=C.BG1, corner_radius=10)
        username_card.pack(fill="x", pady=4)
        
        ctk.CTkLabel(
            username_card, text="Username",
            font=FONT_HEAD, text_color=C.TXT
        ).pack(padx=16, pady=(12, 2), anchor="w")
        
        ctk.CTkLabel(
            username_card,
            text="This is your offline-mode name shown in Minecraft.",
            font=FONT_SMALL, text_color=C.MUT
        ).pack(padx=16, anchor="w")
        
        username_entry = ctk.CTkEntry(
            username_card,
            textvariable=self._username_var,
            placeholder_text="Enter your desired username...",
            fg_color=C.BG2, text_color=C.TXT,
            border_color=C.AC3, font=FONT_BODY,
            height=36
        )
        username_entry.pack(fill="x", padx=16, pady=(4, 14))
        
        # ── RAM ──
        ram_card = ctk.CTkFrame(form, fg_color=C.BG1, corner_radius=10)
        ram_card.pack(fill="x", pady=4)
        
        ram_top = ctk.CTkFrame(ram_card, fg_color="transparent")
        ram_top.pack(fill="x", padx=16, pady=(12, 2))
        
        ctk.CTkLabel(
            ram_top, text="RAM Allocation",
            font=FONT_HEAD, text_color=C.TXT
        ).pack(side="left")
        
        self._ram_value_label = ctk.CTkLabel(
            ram_top, text=f"{self._ram_var.get()} MB",
            font=FONT_HEAD, text_color=C.ACC
        )
        self._ram_value_label.pack(side="right")
        
        ctk.CTkLabel(
            ram_card,
            text="How much RAM to give Minecraft. (1 GB – 16 GB)\n"
                 "💡 4 GB (4096 MB) is recommended for most setups.",
            font=FONT_SMALL, text_color=C.MUT
        ).pack(padx=16, anchor="w")
        
        ram_slider = ctk.CTkSlider(
            ram_card,
            from_=1024, to=16384, number_of_steps=15,
            command=self._on_ram_change,
            button_color=C.ACC, button_hover_color=C.AC2,
            progress_color=C.AC3, fg_color=C.BG2,
            height=16
        )
        ram_slider.set(self._ram_var.get())
        ram_slider.pack(fill="x", padx=16, pady=(8, 14))
        
        # Quick RAM presets
        presets_frame = ctk.CTkFrame(ram_card, fg_color="transparent")
        presets_frame.pack(padx=16, pady=(0, 14))
        
        ctk.CTkLabel(
            presets_frame, text="Quick select:  ", font=FONT_SMALL, text_color=C.MUT
        ).pack(side="left")
        
        for preset in [1024, 2048, 4096, 8192]:
            btn = ctk.CTkButton(
                presets_frame, text=f"{preset//1024} GB" if preset >= 1024 else f"{preset} MB",
                command=lambda v=preset: self._set_ram(v),
                fg_color=C.BG2, hover_color=C.BG3,
                text_color=C.TXT, font=FONT_SMALL,
                border_color=C.AC3, border_width=1,
                corner_radius=6, width=60, height=26
            )
            btn.pack(side="left", padx=3)
        
        # ── Options ──
        options_card = ctk.CTkFrame(form, fg_color=C.BG1, corner_radius=10)
        options_card.pack(fill="x", pady=4)
        
        ctk.CTkLabel(
            options_card, text="Performance & Behavior",
            font=FONT_HEAD, text_color=C.TXT
        ).pack(padx=16, pady=(12, 8), anchor="w")
        
        # FPS Optimizer
        fps_row = ctk.CTkFrame(options_card, fg_color="transparent")
        fps_row.pack(fill="x", padx=16, pady=4)
        
        fps_text = ctk.CTkFrame(fps_row, fg_color="transparent")
        fps_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            fps_text, text="FPS Optimizer",
            font=FONT_BODY, text_color=C.TXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            fps_text, text="Apply Aikar's JVM flags (~30-50% FPS gain)",
            font=FONT_SMALL, text_color=C.MUT
        ).pack(anchor="w")
        
        fps_switch = ctk.CTkSwitch(
            fps_row, text="", variable=self._fps_var,
            onvalue=True, offvalue=False,
            button_color=C.ACC, button_hover_color=C.AC2,
            progress_color=C.AC3, fg_color=C.BG2
        )
        fps_switch.pack(side="right", padx=(8, 0))
        
        # Close on launch
        close_row = ctk.CTkFrame(options_card, fg_color="transparent")
        close_row.pack(fill="x", padx=16, pady=4)
        
        close_text = ctk.CTkFrame(close_row, fg_color="transparent")
        close_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            close_text, text="Close Launcher on Launch",
            font=FONT_BODY, text_color=C.TXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            close_text, text="Minimize to tray when Minecraft starts",
            font=FONT_SMALL, text_color=C.MUT
        ).pack(anchor="w")
        
        close_switch = ctk.CTkSwitch(
            close_row, text="", variable=self._close_var,
            onvalue=True, offvalue=False,
            button_color=C.ACC, button_hover_color=C.AC2,
            progress_color=C.AC3, fg_color=C.BG2
        )
        close_switch.pack(side="right", padx=(8, 0))
        
        # Snapshots
        snap_row = ctk.CTkFrame(options_card, fg_color="transparent")
        snap_row.pack(fill="x", padx=16, pady=(4, 12))
        
        snap_text = ctk.CTkFrame(snap_row, fg_color="transparent")
        snap_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            snap_text, text="Show Snapshot Versions",
            font=FONT_BODY, text_color=C.TXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            snap_text, text="Include experimental snapshot releases in version list",
            font=FONT_SMALL, text_color=C.MUT
        ).pack(anchor="w")
        
        snap_switch = ctk.CTkSwitch(
            snap_row, text="", variable=self._snapshots_var,
            onvalue=True, offvalue=False,
            button_color=C.ACC, button_hover_color=C.AC2,
            progress_color=C.AC3, fg_color=C.BG2
        )
        snap_switch.pack(side="right", padx=(8, 0))
        
        # Profile page is always valid
        self.wizard.can_proceed = True
        self.wizard._update_nav()
    
    def _on_ram_change(self, value: float):
        mb = int(round(value / 512) * 512)
        mb = max(1024, min(16384, mb))
        self._ram_var.set(mb)
        self._ram_value_label.configure(text=f"{mb} MB")
    
    def _set_ram(self, mb: int):
        self._ram_var.set(mb)
        self._ram_value_label.configure(text=f"{mb} MB")
    
    def on_exit(self) -> bool:
        self.wizard.setup_state.username = self._username_var.get().strip() or "UltraPlayer"
        self.wizard.setup_state.memory_mb = self._ram_var.get()
        self.wizard.setup_state.fps_optimize = self._fps_var.get()
        self.wizard.setup_state.close_on_launch = self._close_var.get()
        self.wizard.setup_state.show_snapshots = self._snapshots_var.get()
        return True


# ══════════════════════════════════════════════════════════
#  Step 5: Summary & Complete Page
# ══════════════════════════════════════════════════════════

class SummaryPage(WizardPage):
    """Review all settings before saving."""
    
    def on_enter(self):
        for w in self.winfo_children():
            w.destroy()
        
        state = self.wizard.setup_state
        
        ctk.CTkLabel(
            self, text="🎉  Ready to Go!",
            font=FONT_TITLE, text_color=C.TXT
        ).pack(padx=40, pady=(28, 4), anchor="w")
        
        ctk.CTkLabel(
            self, text="Review your configuration before we save it.",
            font=FONT_BODY, text_color=C.MUT
        ).pack(padx=40, anchor="w")
        
        # ── Summary card ──
        card = ctk.CTkFrame(self, fg_color=C.BG1, corner_radius=12)
        card.pack(fill="x", padx=40, pady=16)
        
        # Sections
        sections = [
            ("👤  Player", [
                ("Username", state.username),
            ]),
            ("☕  Java", [
                ("Status", "✅  Ready" if state.java_path else "⚠  Not set — you can configure later"),
                ("Path", state.java_path if state.java_path else "—"),
            ]),
            ("📂  Game", [
                ("Directory", state.game_dir),
            ]),
            ("⚡  Performance", [
                ("RAM", f"{state.memory_mb} MB"),
                ("FPS Optimizer", "✅  Enabled" if state.fps_optimize else "○  Disabled"),
            ]),
            ("⚙  Behavior", [
                ("Close on Launch", "✅  Yes" if state.close_on_launch else "○  No"),
                ("Show Snapshots", "✅  Yes" if state.show_snapshots else "○  No"),
            ]),
        ]
        
        for section_title, items in sections:
            # Section header
            ctk.CTkLabel(
                card, text=section_title,
                font=FONT_HEAD, text_color=C.ACC
            ).pack(padx=20, pady=(16, 8), anchor="w")
            
            # Items
            for label, value in items:
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=20, pady=2)
                
                ctk.CTkLabel(
                    row, text=label,
                    font=FONT_SMALL, text_color=C.MUT,
                    width=140, anchor="w"
                ).pack(side="left")
                
                ctk.CTkLabel(
                    row, text=str(value),
                    font=FONT_BODY, text_color=C.TXT,
                    anchor="w"
                ).pack(side="left", padx=(8, 0))
        
        # Bottom padding
        ctk.CTkFrame(card, fg_color="transparent", height=12).pack()
        
        # ── Notes ──
        notes_card = ctk.CTkFrame(self, fg_color=C.BG2, corner_radius=10)
        notes_card.pack(fill="x", padx=40, pady=(8, 0))
        
        if not state.java_path:
            ctk.CTkLabel(
                notes_card,
                text="⚠  Note: You didn't set up Java. You can configure it later in Settings.",
                font=FONT_SMALL, text_color=C.GLD
            ).pack(padx=16, pady=10, anchor="w")
        else:
            ctk.CTkLabel(
                notes_card,
                text="💡  You can change any of these settings later from the Settings page.",
                font=FONT_SMALL, text_color=C.MUT
            ).pack(padx=16, pady=10, anchor="w")
        
        # Summary page — always allow finishing
        self.wizard.can_proceed = True
        self.wizard._update_nav()
    
    def on_finish(self) -> bool:
        """Save the configuration."""
        state = self.wizard.setup_state
        
        # Ensure directories exist
        APP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Build config
        config = {
            "username": state.username,
            "memory_mb": state.memory_mb,
            "java_path": state.java_path,
            "game_dir": state.game_dir,
            "fps_optimize": state.fps_optimize,
            "version": state.version,
            "loader": state.loader,
            "active_profile": "default",
            "custom_jvm": "",
            "close_on_launch": state.close_on_launch,
            "show_snapshots": state.show_snapshots,
            "check_updates": True,
            "first_run_complete": True,
        }
        
        # Build default profile
        profiles = [
            {
                "id": "default",
                "name": "Default",
                "color": "#12c8ff",
                "version": state.version,
                "loader": state.loader,
                "memory_mb": state.memory_mb,
                "mods": [],
                "active_shader": "",
                "java_args": "",
                "resolution_width": 0,
                "resolution_height": 0,
                "fullscreen": False,
            }
        ]
        
        # Atomic write
        try:
            tmp = CONFIG_FILE.with_suffix(f".tmp.{os.getpid()}")
            tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
            tmp.replace(CONFIG_FILE)
            
            tmp2 = PROFILES_FILE.with_suffix(f".tmp.{os.getpid()}")
            tmp2.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
            tmp2.replace(PROFILES_FILE)
            
            state.completed = True
            return True
            
        except (OSError, IOError) as e:
            messagebox.showerror(
                "Save Error",
                f"Could not save configuration:\n{e}\n\n"
                "Check permissions on ~/.ultrawater/"
            )
            return False


# ══════════════════════════════════════════════════════════
#  Main Wizard Window
# ══════════════════════════════════════════════════════════

class InstallWizard(ctk.CTkToplevel):
    """
    The main setup wizard — a multi-page dialog with:
      - Step indicator sidebar
      - Page content area
      - Back/Next/Finish navigation
      - First-run detection
    """
    
    def __init__(self, parent: Optional[ctk.CTk] = None, setup_state: Optional[SetupState] = None):
        super().__init__(parent)
        
        self.setup_state = setup_state or SetupState()
        self.can_proceed = False
        self._current_step = 0
        self._pages: List[WizardPage] = []
        
        # ── Window setup ──
        self.title(WIZARD_TITLE)
        self.geometry(WIZARD_SIZE)
        self.minsize(*WIZARD_MIN_SIZE)
        self.configure(fg_color=C.BG0)
        
        # Center on parent or screen
        if parent:
            x = parent.winfo_x() + (parent.winfo_width() - 760) // 2
            y = parent.winfo_y() + (parent.winfo_height() - 620) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        else:
            self.after(100, self._center_on_screen)
        
        # ── Layout ──
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._build_sidebar()
        self._build_content()
        self._build_navbar()
        
        # ── Load pages ──
        self._load_pages()
        
        # ── Show first page ──
        self.after(200, self._show_page, 0)
        
        # ── Modal ──
        self.after(100, self.grab_set)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _center_on_screen(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")
    
    def _build_sidebar(self):
        """Build the step indicator on the left side."""
        self._sidebar = ctk.CTkFrame(self, fg_color=C.BG1, corner_radius=0, width=200)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        
        # Logo at top
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.pack(pady=(24, 20), padx=16, anchor="w")
        
        dot = ctk.CTkFrame(logo_frame, fg_color=C.ACC, corner_radius=50, width=28, height=28)
        dot.pack(side="left")
        dot.pack_propagate(False)
        ctk.CTkLabel(dot, text="UW", font=("Consolas", 11, "bold"),
                     text_color=C.BG0).pack(expand=True)
        
        ctk.CTkLabel(
            logo_frame, text="Setup",
            font=("Consolas", 13, "bold"), text_color=C.ACC
        ).pack(side="left", padx=(8, 0))
        
        # Separator
        ctk.CTkFrame(self._sidebar, height=1, fg_color=C.AC3).pack(
            fill="x", padx=12, pady=4)
        
        # Step indicators
        self._step_labels: List[ctk.CTkFrame] = []
        self._step_rows: List[ctk.CTkFrame] = []
        step_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        step_frame.pack(fill="x", padx=12, pady=16)
        
        for i, step_name in enumerate(STEPS):
            row = ctk.CTkFrame(step_frame, fg_color="transparent")
            row.pack(fill="x", pady=6)
            self._step_rows.append(row)
            
            # Step number circle
            num = ctk.CTkFrame(row, width=26, height=26,
                               fg_color=C.BG2, corner_radius=13)
            num.pack(side="left")
            num.pack_propagate(False)
            self._step_labels.append(num)
            
            ctk.CTkLabel(
                num, text=str(i + 1),
                font=("Consolas", 11, "bold"),
                text_color=C.MUT
            ).pack(expand=True)
            
            # Step name
            ctk.CTkLabel(
                row, text=step_name,
                font=("Consolas", 11),
                text_color=C.MUT
            ).pack(side="left", padx=(8, 0))
        
        # Spacer + footer
        ctk.CTkFrame(self._sidebar, fg_color="transparent").pack(expand=True)
        
        # Version at bottom
        ctk.CTkLabel(
            self._sidebar, text="v2.0.0",
            font=FONT_SMALL, text_color=C.AC3
        ).pack(pady=(0, 12), padx=16, anchor="w")
    
    def _build_content(self):
        """Build the content area for pages."""
        self._content = ctk.CTkFrame(self, fg_color=C.BG0, corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)
    
    def _build_navbar(self):
        """Build the bottom navigation bar."""
        self._navbar = ctk.CTkFrame(self, fg_color=C.BG1, corner_radius=0, height=56)
        self._navbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._navbar.grid_propagate(False)
        
        # Status text
        self._status_label = ctk.CTkLabel(
            self._navbar, text="",
            font=FONT_SMALL, text_color=C.MUT
        )
        self._status_label.pack(side="left", padx=16)
        
        # Navigation buttons
        btn_frame = ctk.CTkFrame(self._navbar, fg_color="transparent")
        btn_frame.pack(side="right", padx=16)
        
        self._back_btn = ctk.CTkButton(
            btn_frame, text="←  Back",
            command=self._prev_step,
            fg_color=C.BG2, hover_color=C.BG3,
            text_color=C.TXT, font=FONT_BODY,
            border_color=C.AC3, border_width=1,
            corner_radius=8, width=100, height=36
        )
        self._back_btn.pack(side="left", padx=4)
        
        self._next_btn = ctk.CTkButton(
            btn_frame, text="Next  →",
            command=self._next_step,
            fg_color=C.ACC, hover_color=C.AC2,
            text_color=C.BG0, font=FONT_HEAD,
            corner_radius=8, width=120, height=36
        )
        self._next_btn.pack(side="left", padx=4)
    
    def _load_pages(self):
        """Create all wizard pages."""
        self._pages = [
            WelcomePage(self._content),
            JavaPage(self._content),
            DirectoryPage(self._content),
            ProfilePage(self._content),
            SummaryPage(self._content),
        ]
        
        for page in self._pages:
            page.grid(row=0, column=0, sticky="nsew")
    
    def _show_page(self, index: int):
        """Display the page at the given index."""
        if index < 0 or index >= len(self._pages):
            return
        
        self._current_step = index
        
        # Hide all pages, show current
        for i, page in enumerate(self._pages):
            if i == index:
                page.grid(row=0, column=0, sticky="nsew")
                page.on_enter()
            else:
                page.grid_forget()
        
        # Update sidebar
        for i, (num_frame, step_row) in enumerate(zip(self._step_labels, self._step_rows)):
            if i < index:
                # Completed step
                num_frame.configure(fg_color=C.GRN)
                for child in num_frame.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text="✓", text_color=C.BG0)
                for child in step_row.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text_color=C.GRN)
            elif i == index:
                # Current step
                num_frame.configure(fg_color=C.ACC)
                for child in num_frame.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text=str(i + 1), text_color=C.BG0)
                for child in step_row.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text_color=C.TXT)
            else:
                # Future step
                num_frame.configure(fg_color=C.BG2)
                for child in num_frame.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text=str(i + 1), text_color=C.MUT)
                for child in step_row.winfo_children():
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text_color=C.MUT)
        
        # Update nav buttons
        is_first = index == 0
        is_last = index == len(self._pages) - 1
        
        self._back_btn.configure(state="disabled" if is_first else "normal")
        
        if is_last:
            self._next_btn.configure(text="✓  Finish Setup", command=self._finish)
        else:
            self._next_btn.configure(text="Next  →", command=self._next_step)
        
        # Start disabled until page allows it
        self._next_btn.configure(state="disabled")
        self._status_label.configure(text="")
        
        # Page can override after setup
        self.after(100, self._update_nav)
    
    def _update_nav(self):
        """Enable/disable the Next button based on page state."""
        if self.can_proceed:
            self._next_btn.configure(state="normal")
            self._status_label.configure(text="")
        else:
            is_last = self._current_step == len(self._pages) - 1
            if not is_last:
                self._status_label.configure(
                    text="Complete this step to continue →",
                    text_color=C.GLD
                )
    
    def _next_step(self):
        """Advance to the next step."""
        current = self._pages[self._current_step]
        
        # Validate current page before leaving
        if not current.on_exit():
            return
        
        next_idx = self._current_step + 1
        if next_idx < len(self._pages):
            self.can_proceed = False
            self._show_page(next_idx)
    
    def _prev_step(self):
        """Go back to the previous step."""
        prev_idx = self._current_step - 1
        if prev_idx >= 0:
            self.can_proceed = True
            self._show_page(prev_idx)
    
    def _finish(self):
        """Complete the wizard and save configuration."""
        current = self._pages[self._current_step]
        if current.on_finish():
            self.setup_state.completed = True
            self.grab_release()
            self.destroy()
    
    def _on_close(self):
        """Handle window close — ask if user really wants to cancel."""
        if messagebox.askyesno(
            "Cancel Setup?",
            "Are you sure you want to cancel?\n\n"
            "The launcher may not work correctly without configuration."
        ):
            self.grab_release()
            self.destroy()


# ══════════════════════════════════════════════════════════
#  Public API — Integration Points
# ══════════════════════════════════════════════════════════

def is_first_run() -> bool:
    """
    Check if this is the first time the launcher has been run.
    
    Returns True if no config.json exists or first_run_complete is missing.
    """
    config_path = CONFIG_FILE
    
    if not config_path.exists():
        return True
    
    try:
        config = json.loads(config_path.read_text("utf-8"))
        return not config.get("first_run_complete", False)
    except (json.JSONDecodeError, OSError, IOError):
        return True


def should_run_wizard() -> bool:
    """
    More nuanced check — returns True if:
      - First run (no config)
      - Java not configured and not found via PATH
      - No game directory configured
    """
    if not CONFIG_FILE.exists():
        return True
    
    try:
        config = json.loads(CONFIG_FILE.read_text("utf-8"))
        
        # First run flag
        if not config.get("first_run_complete", False):
            return True
        
        # Java check
        java_path = config.get("java_path", "")
        if not java_path or not Path(java_path).exists():
            # Check if Java is available via PATH
            found = find_java()
            if not found:
                return False  # Don't bother the user if we can't auto-detect
        
        return False
        
    except (json.JSONDecodeError, OSError, IOError):
        return True


def run_setup_wizard(parent: Optional[ctk.CTk] = None) -> SetupState:
    """
    Run the setup wizard and return the resulting configuration state.
    
    This is the main entry point. Call it like:
    
        from wizard import run_setup_wizard, is_first_run
        
        if is_first_run():
            state = run_setup_wizard(app)
            if not state.completed:
                # User cancelled — handle gracefully
    
    Args:
        parent: Optional parent tkinter window
    
    Returns:
        SetupState with the user's choices (state.completed indicates success)
    """
    wizard = InstallWizard(parent)
    parent.wait_window(wizard) if parent else wizard.wait_window()
    return wizard.setup_state


def ensure_setup(app: Optional[ctk.CTk] = None) -> bool:
    """
    Convenience function: check if setup is needed, run wizard if so.
    
    Call this at launcher startup:
    
        from wizard import ensure_setup
        if not ensure_setup(self):
            # User cancelled setup — exit gracefully
            self.destroy()
            sys.exit(0)
    
    Returns True if setup is complete or was skipped (already configured).
    """
    if not is_first_run():
        return True
    
    state = run_setup_wizard(app)
    return state.completed