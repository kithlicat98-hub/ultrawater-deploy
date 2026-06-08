#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ULTRAWATER CLIENT  v2.0.0                                          ║
║          Ultralight Minecraft Launcher                                      ║
║                                                                             ║
║  Requirements:  pip install customtkinter                                   ║
║                 pip install minecraft-launcher-lib>=8.0                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import json
import logging
import os
import sys
import subprocess
import shutil
import platform
import uuid
import webbrowser
import re
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any
from queue import Queue, Empty

# ── Wizard Integration ────────────────────────────────────
try:
    from wizard import ensure_setup, is_first_run, run_setup_wizard
    HAS_WIZARD = True
except ImportError:
    HAS_WIZARD = False

# ── Minecraft launcher lib ────────────────────────────────
try:
    import minecraft_launcher_lib as mclib
    HAS_MCLIB = True
    MCLIB_VER = tuple(int(x) for x in getattr(mclib, "__version__", "0").split(".")[:2])
    HAS_MOD_LOADER = MCLIB_VER >= (8, 0)
except ImportError:
    HAS_MCLIB = False
    HAS_MOD_LOADER = False
    MCLIB_VER = (0, 0)


# ══════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════

VERSION      = "2.0.0"
APP_NAME     = "UltraWater Client"
WINDOW_SIZE  = "1024x680"
MIN_SIZE     = (860, 580)

APP_DIR      = Path.home() / ".ultrawater"
MC_DIR       = Path.home() / ".minecraft"
CONFIG_FILE  = APP_DIR / "config.json"
PROFILES_FILE= APP_DIR / "profiles.json"
APP_LOG_FILE = APP_DIR / "app.log"

APP_DIR.mkdir(parents=True, exist_ok=True)
(APP_DIR / "profiles").mkdir(exist_ok=True)

class Colors:
    BG0 = "#020b18"; BG1 = "#041c30"; BG2 = "#072d4a"
    BG3 = "#0d3d5c"; ACC = "#12c8ff"; AC2 = "#0a9fd4"
    AC3 = "#064d6e"; TXT = "#e8f6ff"; MUT = "#7ab8d4"
    GRN = "#39ff7a"; GLD = "#f0b030"; RED = "#ff5050"

FONT_TITLE = ("Consolas", 20, "bold")
FONT_HEAD  = ("Consolas", 13, "bold")
FONT_BODY  = ("Consolas", 12)
FONT_SMALL = ("Consolas", 10)
FONT_MONO  = ("Courier New", 11)

POPULAR_VERSIONS = ["26.1.2","1.21.4","1.21.1","1.20.4","1.20.1","1.19.4","1.19.2","1.18.2","1.17.1","1.16.5","1.12.2","1.8.9"]
LOADER_CHOICES = ["vanilla","fabric","forge","quilt","neoforge"]

AIKAR_FLAGS = ["-XX:+UseG1GC","-XX:+ParallelRefProcEnabled","-XX:MaxGCPauseMillis=200","-XX:+UnlockExperimentalVMOptions","-XX:+DisableExplicitGC","-XX:+AlwaysPreTouch","-XX:G1NewSizePercent=30","-XX:G1MaxNewSizePercent=40","-XX:G1HeapRegionSize=8M","-XX:G1ReservePercent=20","-XX:G1HeapWastePercent=5","-XX:G1MixedGCCountTarget=4","-XX:InitiatingHeapOccupancyPercent=15","-XX:G1MixedGCLiveThresholdPercent=90","-XX:G1RSetUpdatingPauseTimePercent=5","-XX:SurvivorRatio=32","-XX:+PerfDisableSharedMem","-XX:MaxTenuringThreshold=1"]

DEFAULT_CONFIG = {"username":"UltraPlayer","memory_mb":4096,"java_path":"","game_dir":str(MC_DIR),"fps_optimize":True,"version":"26.1.2","loader":"vanilla","active_profile":"default","custom_jvm":"","close_on_launch":False,"show_snapshots":False,"check_updates":True,"first_run_complete":False}
DEFAULT_PROFILES = [{"id":"default","name":"Default","color":"#12c8ff","version":"26.1.2","loader":"vanilla","memory_mb":4096,"mods":[],"active_shader":"","java_args":"","resolution_width":0,"resolution_height":0,"fullscreen":False}]


# ══════════════════════════════════════════════════════════
#  Logging Setup
# ══════════════════════════════════════════════════════════

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("ultrawater")
    logger.setLevel(logging.DEBUG)
    if logger.handlers: return logger
    try:
        fh = logging.FileHandler(APP_LOG_FILE, encoding="utf-8", mode="a")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except: pass
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    return logger


# ══════════════════════════════════════════════════════════
#  Data Store
# ══════════════════════════════════════════════════════════

class DataStore:
    def __init__(self, log: logging.Logger):
        self.log = log
        self._lock = threading.Lock()
        self._config = {}
        self._profiles = []
        self._load()
    
    def _load(self):
        self._config = self._read(CONFIG_FILE, DEFAULT_CONFIG)
        self._profiles = self._read(PROFILES_FILE, DEFAULT_PROFILES)
        for k, v in DEFAULT_CONFIG.items():
            self._config.setdefault(k, v)
        if not self._profiles:
            self._profiles = list(DEFAULT_PROFILES)
    
    def _read(self, path, default):
        if not path.exists():
            return json.loads(json.dumps(default))
        try:
            return json.loads(path.read_text("utf-8"))
        except:
            return json.loads(json.dumps(default))
    
    def save(self):
        with self._lock:
            self._atomic(CONFIG_FILE, self._config)
            self._atomic(PROFILES_FILE, self._profiles)
    
    def _atomic(self, path, data):
        tmp = path.with_suffix(f".tmp.{os.getpid()}")
        try:
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(path)
        except: pass
        finally: tmp.unlink(missing_ok=True)
    
    @property
    def config(self): return self._config
    
    @property
    def profiles(self): return self._profiles
    
    def active_profile(self):
        pid = self._config.get("active_profile","default")
        for p in self._profiles:
            if p["id"] == pid: return p
        return self._profiles[0] if self._profiles else DEFAULT_PROFILES[0]
    
    def get_profile(self, pid):
        for p in self._profiles:
            if p["id"] == pid: return p
        return None
    
    def create_profile(self, name, version, loader):
        pid = uuid.uuid4().hex[:8]
        p = {"id":pid,"name":name,"color":"#12c8ff","version":version,"loader":loader,"memory_mb":self._config["memory_mb"],"mods":[],"active_shader":"","java_args":"","resolution_width":0,"resolution_height":0,"fullscreen":False}
        self._profiles.append(p)
        self.save()
        return p
    
    def delete_profile(self, pid):
        self._profiles = [p for p in self._profiles if p["id"] != pid]
        if self._config.get("active_profile") == pid:
            self._config["active_profile"] = self._profiles[0]["id"] if self._profiles else "default"
        self.save()
    
    def mods_dir(self, prof):
        d = APP_DIR / "profiles" / prof["id"] / "mods"
        d.mkdir(parents=True, exist_ok=True); return d
    
    def shaders_dir(self, prof):
        d = APP_DIR / "profiles" / prof["id"] / "shaderpacks"
        d.mkdir(parents=True, exist_ok=True); return d


# ══════════════════════════════════════════════════════════
#  Minecraft Manager
# ══════════════════════════════════════════════════════════

class MinecraftManager:
    def __init__(self, store: DataStore, log: logging.Logger, log_queue: Queue):
        self.store = store; self.log = log; self.log_queue = log_queue
        self.process = None; self._launch_lock = threading.Lock()
    
    def _log(self, msg, level="INFO"):
        getattr(self.log, level.lower(), self.log.info)(msg)
        self.log_queue.put_nowait(f"[{level}] {msg}")
    
    def _find_java(self):
        cfg = self.store.config
        jp = cfg.get("java_path","").strip()
        if jp:
            p = Path(jp)
            if p.exists(): return str(p.resolve())
            ext = ".exe" if platform.system()=="Windows" else ""
            for c in ["java",f"java{ext}"]:
                cp = p/"bin"/c
                if cp.exists(): return str(cp.resolve())
        jh = os.environ.get("JAVA_HOME","")
        if jh:
            ext = ".exe" if platform.system()=="Windows" else ""
            cp = Path(jh)/"bin"/f"java{ext}"
            if cp.exists(): return str(cp.resolve())
        found = shutil.which("java.exe" if platform.system()=="Windows" else "java")
        if found: return found
        paths = ["/usr/lib/jvm/java-25-openjdk/bin/java","/usr/lib/jvm/java-21-openjdk/bin/java","/usr/lib/jvm/default-java/bin/java","/usr/local/opt/openjdk/bin/java"]
        if platform.system()=="Windows":
            paths = [r"C:\Program Files\Java\jdk-25\bin\java.exe",r"C:\Program Files\Eclipse Adoptium\jre-25\bin\java.exe",r"C:\Program Files\Temurin\bin\java.exe"]
        for cp in paths:
            if Path(cp).exists(): return cp
        return "java"
    
    def get_java_info(self):
        java = self._find_java()
        info = {"path":java,"version":"Unknown","arch":"Unknown"}
        try:
            r = subprocess.run([java,"-XshowSettings:properties","-version"],capture_output=True,text=True,timeout=10)
            o = r.stdout+r.stderr
            m = re.search(r'java\s+version\s+"([^"]+)"',o)
            if m: info["version"]=m.group(1)
            m = re.search(r'os\.arch\s*=\s*(\S+)',o)
            if m: info["arch"]=m.group(1)
        except: pass
        return info
    
    def is_java_ok(self):
        info = self.get_java_info()
        if "Error" in info["version"] or info["version"]=="Unknown": return False
        m = re.search(r'(?:version\s+")?(?:1\.)?(\d+)',info["version"])
        return m and int(m.group(1))>=25
    
    def launch(self, prof):
        if not self._launch_lock.acquire(blocking=False):
            self._log("Already launching","WARNING"); return
        try:
            cfg = self.store.config
            gd = cfg["game_dir"]; mv = prof.get("version",cfg["version"])
            ld = prof.get("loader",cfg.get("loader","vanilla"))
            mm = prof.get("memory_mb",cfg.get("memory_mb",4096))
            un = cfg.get("username","UltraPlayer") or "UltraPlayer"
            self._log(f"Launching {mv} ({ld}) with {mm}MB for {un}")
            if not HAS_MCLIB:
                self._log("minecraft_launcher_lib not installed","ERROR"); return
            try:
                jp = self._find_java()
                ji = self.get_java_info()
                self._log(f"Java: {ji['version']} at {jp}")
                opts = mclib.types.MinecraftOptions(username=un,uuid="",token="",launcherName=APP_NAME,launcherVersion=VERSION,gameDirectory=gd,jvmArguments=[f"-Xms{max(mm//2,512)}m",f"-Xmx{mm}m"]+(AIKAR_FLAGS if cfg.get("fps_optimize",True) else []))
                installed = {v["id"] for v in mclib.utils.get_installed_versions(gd)}
                if mv not in installed:
                    self._log(f"Installing {mv}...")
                    mclib.install.install_minecraft_version(mv,gd)
                mc_id = mv
                if ld=="fabric":
                    if not any("fabric" in v and mv in v for v in installed):
                        lv = mclib.mod_loader.get_latest_loader_version("fabric") if HAS_MOD_LOADER else mclib.fabric.get_latest_loader_version()
                        if HAS_MOD_LOADER: mclib.mod_loader.install_mod_loader("fabric",mv,gd,loader_version=lv)
                        else: mclib.fabric.install_fabric(mv,gd,loader_version=lv)
                        mc_id = f"fabric-loader-{lv}-{mv}"
                cmd = mclib.command.get_minecraft_command(mc_id,gd,opts)
                cmd[0]=jp
                si = None
                if platform.system()=="Windows":
                    si=subprocess.STARTUPINFO(); si.dwFlags|=subprocess.STARTF_USESHOWWINDOW
                self.process = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,startupinfo=si)
                self._log(f"PID: {self.process.pid}")
                if self.process.stdout:
                    for line in iter(self.process.stdout.readline,""):
                        l=line.rstrip()
                        if l: self._log(l)
                self.process.wait()
                self._log(f"Exited code {self.process.returncode}")
            except Exception as e:
                self._log(f"Launch failed: {e}","ERROR"); self._log(traceback.format_exc(),"DEBUG")
            finally: self.process=None
        finally: self._launch_lock.release()
    
    def kill(self):
        if self.process and self.process.poll() is None:
            self._log("Terminating...")
            try:
                self.process.terminate()
                try: self.process.wait(timeout=5)
                except: self.process.kill(); self.process.wait()
                self._log("Terminated")
            except: pass
    
    @property
    def is_running(self): return self.process is not None and self.process.poll() is None


# ══════════════════════════════════════════════════════════
#  UI Helpers
# ══════════════════════════════════════════════════════════

def tf(parent, c=Colors.BG1, **kw): return ctk.CTkFrame(parent, fg_color=c, **kw)
def tl(parent, t, f=FONT_BODY, c=Colors.TXT, **kw): return ctk.CTkLabel(parent, text=t, font=f, text_color=c, **kw)
def tb(parent, t, cmd, primary=True, w=130, h=34, **kw):
    if primary: return ctk.CTkButton(parent,text=t,command=cmd,fg_color=Colors.ACC,hover_color=Colors.AC2,text_color=Colors.BG0,font=FONT_HEAD,corner_radius=6,width=w,height=h,**kw)
    return ctk.CTkButton(parent,text=t,command=cmd,fg_color=Colors.BG2,hover_color=Colors.BG3,text_color=Colors.TXT,border_color=Colors.AC3,border_width=1,font=FONT_BODY,corner_radius=6,width=w,height=h,**kw)

def sh(parent, title):
    r = tf(parent, "transparent"); r.pack(fill="x", pady=(16,4))
    tl(r, title, FONT_SMALL, Colors.MUT).pack(side="left")
    ctk.CTkFrame(r, height=1, fg_color=Colors.AC3, corner_radius=0).pack(side="left", fill="x", expand=True, padx=(8,0), pady=6)

def od(path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        if platform.system()=="Windows": os.startfile(str(path))
        elif platform.system()=="Darwin": subprocess.Popen(["open",str(path)])
        else: subprocess.Popen(["xdg-open",str(path)])
    except: pass


# ══════════════════════════════════════════════════════════
#  Pages: Home, Settings, Profiles, Mods, Shaders, Console
# ══════════════════════════════════════════════════════════

class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
    
    def refresh(self):
        for w in self.winfo_children(): w.destroy()
        self._build(self.app.store.config, self.app.store.active_profile())
    
    def _build(self, cfg, prof):
        banner = tf(self, Colors.BG1, corner_radius=12)
        banner.pack(fill="x", padx=20, pady=(20,0))
        banner.grid_columnconfigure(1, weight=1)
        dot = tf(banner, Colors.ACC, corner_radius=50)
        dot.grid(row=0, column=0, rowspan=2, padx=20, pady=20)
        ctk.CTkLabel(dot, text="UW", font=("Consolas",16,"bold"), text_color=Colors.BG0, width=48, height=48).pack(padx=8,pady=8)
        tl(banner, f"Welcome, {cfg['username']}", FONT_TITLE, Colors.TXT).grid(row=0,column=1,sticky="w",pady=(14,0))
        tl(banner, f"UltraWater Client v{VERSION}", Colors.MUT).grid(row=1,column=1,sticky="w")
        jok = self.app.minecraft.is_java_ok()
        sc = Colors.GRN if jok else Colors.RED
        st = "Java ✓ Ready" if jok else "Java ✗ Missing"
        pill = tf(banner, Colors.BG2, corner_radius=20)
        pill.grid(row=0,column=2,rowspan=2,padx=20)
        ind = ctk.CTkFrame(pill, width=10, height=10, fg_color=sc, corner_radius=5)
        ind.pack(side="left", padx=(12,4))
        tl(pill, st, FONT_SMALL, sc).pack(side="left", padx=(0,12), pady=10)
        if not jok:
            ft = tf(self, Colors.BG2, corner_radius=8); ft.pack(fill="x", padx=20, pady=(8,0))
            tl(ft, "Java 25+ required. Install from adoptium.net", Colors.GLD, FONT_SMALL, wraplength=700).pack(padx=14,pady=8)
        sh(self, "ACTIVE PROFILE")
        pc = tf(self, Colors.BG1, corner_radius=10); pc.pack(fill="x", padx=20); pc.grid_columnconfigure(0, weight=1)
        for i,(k,v) in enumerate([("Profile",prof["name"]),("Version",prof["version"]),("Loader",prof.get("loader","vanilla").title()),("Memory",f"{prof.get('memory_mb',cfg['memory_mb'])} MB"),("Game dir",cfg["game_dir"])]):
            r = tf(pc, "transparent"); r.grid(row=i,column=0,sticky="ew",padx=16,pady=2)
            tl(r, f"{k}:", FONT_SMALL, Colors.MUT, width=80, anchor="w").pack(side="left")
            tl(r, str(v), Colors.TXT, anchor="w").pack(side="left")
        sh(self, "SYSTEM")
        sc_frame = tf(self, "transparent"); sc_frame.pack(fill="x", padx=20)
        ji = self.app.minecraft.get_java_info()
        for i,(k,v) in enumerate([("Java",f"{ji['version']} ({ji['arch']})"),("Platform",f"{platform.system()} {platform.release()}"),("FPS Opt","✓ Enabled" if cfg.get("fps_optimize",True) else "○ Disabled")]):
            r = tf(sc_frame, "transparent"); r.grid(row=i,column=0,sticky="ew",padx=16,pady=2); sc_frame.grid_columnconfigure(0,weight=1)
            tl(r, f"{k}:", FONT_SMALL, Colors.MUT, width=80, anchor="w").pack(side="left")
            tl(r, str(v), Colors.TXT, anchor="w").pack(side="left")


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent"); self.app = app; self._wm = {}; self._build()
    
    def _build(self):
        tl(self, "Settings", FONT_TITLE).pack(anchor="w", padx=20, pady=(20,0))
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        cfg = self.app.store.config
        sh(scroll, "PLAYER"); self._er(scroll, "Username", "Offline username", "username", cfg["username"])
        sh(scroll, "PERFORMANCE"); self._mr(scroll, cfg["memory_mb"])
        self._tr(scroll, "FPS Optimizer", "Aikar's JVM flags (~30-50% FPS)", "fps_optimize", cfg["fps_optimize"])
        sh(scroll, "JAVA")
        ji = self.app.minecraft.get_java_info(); jc = Colors.GRN if "Error" not in ji["version"] else Colors.RED
        jf = tf(scroll, Colors.BG1, corner_radius=8); jf.pack(fill="x",padx=20,pady=3)
        tl(jf, f"Detected: {ji['version']} ({ji['arch']})", jc, FONT_SMALL).pack(padx=14,pady=8)
        self._er(scroll, "Java Path", "Leave blank for auto-detect", "java_path", cfg.get("java_path",""))
        sh(scroll, "DIRECTORIES"); self._dr(scroll, "Game Directory", "Where Minecraft is installed", "game_dir", cfg["game_dir"])
        sh(scroll, "ADVANCED")
        self._er(scroll, "Custom JVM Args", "Extra JVM arguments", "custom_jvm", cfg.get("custom_jvm",""))
        self._tr(scroll, "Close on Launch", "Hide launcher when game starts", "close_on_launch", cfg.get("close_on_launch",False))
        tf(scroll, "transparent").pack(pady=8); tb(scroll, "Save Settings", self._save, w=160).pack(padx=20,anchor="w")
        tl(scroll, "Saved to ~/.ultrawater/config.json", Colors.MUT, FONT_SMALL).pack(padx=20,pady=(4,20))
    
    def _er(self, p, label, hint, key, default):
        r = tf(p, Colors.BG1, corner_radius=8); r.pack(fill="x", padx=20, pady=3); r.grid_columnconfigure(1,weight=1)
        l = tf(r,"transparent"); l.grid(row=0,column=0,sticky="w",padx=14,pady=10)
        tl(l, label, FONT_HEAD, Colors.TXT, anchor="w").pack(anchor="w"); tl(l, hint, Colors.MUT, FONT_SMALL, anchor="w").pack(anchor="w")
        var = ctk.StringVar(value=str(default))
        ctk.CTkEntry(r, textvariable=var, fg_color=Colors.BG2, text_color=Colors.TXT, border_color=Colors.AC3, width=240).grid(row=0,column=1,padx=14,pady=10,sticky="e")
        self._wm[key] = var
    
    def _dr(self, p, label, hint, key, default):
        r = tf(p, Colors.BG1, corner_radius=8); r.pack(fill="x", padx=20, pady=3); r.grid_columnconfigure(1,weight=1)
        l = tf(r,"transparent"); l.grid(row=0,column=0,sticky="w",padx=14,pady=10)
        tl(l, label, FONT_HEAD, Colors.TXT, anchor="w").pack(anchor="w"); tl(l, hint, Colors.MUT, FONT_SMALL, anchor="w").pack(anchor="w")
        rt = tf(r,"transparent"); rt.grid(row=0,column=1,padx=14,pady=10,sticky="e")
        var = ctk.StringVar(value=str(default))
        ctk.CTkEntry(rt, textvariable=var, fg_color=Colors.BG2, text_color=Colors.TXT, border_color=Colors.AC3, width=200).pack(side="left",padx=(0,4))
        tb(rt, "Browse", lambda: var.set(filedialog.askdirectory(title=label) or var.get()), False, 70, 30).pack(side="left")
        self._wm[key] = var
    
    def _mr(self, p, default_mb):
        r = tf(p, Colors.BG1, corner_radius=8); r.pack(fill="x", padx=20, pady=3)
        top = tf(r,"transparent"); top.pack(fill="x",padx=14,pady=(10,2))
        tl(top, "RAM Allocation", FONT_HEAD, Colors.TXT).pack(side="left")
        self._ml = tl(top, f"{default_mb} MB", Colors.ACC, FONT_HEAD); self._ml.pack(side="right")
        self._ms = ctk.CTkSlider(r, from_=1024, to=16384, number_of_steps=31, command=lambda v: self._ml.configure(text=f"{int(round(v/512)*512)} MB"), button_color=Colors.ACC, button_hover_color=Colors.AC2, progress_color=Colors.AC3, fg_color=Colors.BG2)
        self._ms.set(default_mb); self._ms.pack(fill="x",padx=14,pady=(4,12))
    
    def _tr(self, p, label, hint, key, default):
        r = tf(p, Colors.BG1, corner_radius=8); r.pack(fill="x", padx=20, pady=3); r.grid_columnconfigure(0,weight=1)
        l = tf(r,"transparent"); l.grid(row=0,column=0,sticky="w",padx=14,pady=10)
        tl(l, label, FONT_HEAD, Colors.TXT, anchor="w").pack(anchor="w"); tl(l, hint, Colors.MUT, FONT_SMALL, anchor="w").pack(anchor="w")
        var = ctk.BooleanVar(value=default)
        ctk.CTkSwitch(r, text="", variable=var, onvalue=True, offvalue=False, button_color=Colors.ACC, button_hover_color=Colors.AC2, progress_color=Colors.AC3, fg_color=Colors.BG2, width=46, height=22).grid(row=0,column=1,padx=14)
        self._wm[key] = var
    
    def _save(self):
        cfg = self.app.store.config
        for k,var in self._wm.items():
            v = var.get(); cfg[k] = v if isinstance(v, bool) else v
        mb = int(round(self._ms.get()/512)*512); cfg["memory_mb"] = max(1024,min(16384,mb))
        self.app.store.save(); self.app.navigate_to("home"); messagebox.showinfo("Saved","Settings saved!")


class ProfilesPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent"); self.app = app; self._build()
    
    def _build(self):
        h = tf(self,"transparent"); h.pack(fill="x",padx=20,pady=(20,0))
        tl(h, "Profiles", FONT_TITLE).pack(side="left"); tb(h, "+ New Profile", self._cd, w=130).pack(side="right")
        tl(self, "Each profile has its own version, loader, mods and shaders.", Colors.MUT, FONT_SMALL).pack(padx=20,anchor="w",pady=(4,0))
        tf(self, height=1, fg_color=Colors.AC3, corner_radius=0).pack(fill="x",padx=20,pady=8)
        self._lf = ctk.CTkScrollableFrame(self, fg_color=Colors.BG1, corner_radius=10)
        self._lf.pack(fill="both", expand=True, padx=20, pady=(0,20)); self.refresh()
    
    def refresh(self):
        for w in self._lf.winfo_children(): w.destroy()
        for prof in self.app.store.profiles:
            ia = prof["id"] == self.app.store.config["active_profile"]
            r = tf(self._lf, Colors.BG3 if ia else Colors.BG2, corner_radius=8); r.pack(fill="x",padx=8,pady=4); r.grid_columnconfigure(1,weight=1)
            sw = tf(r, prof.get("color",Colors.ACC), corner_radius=6); sw.grid(row=0,column=0,padx=(10,0),pady=12,sticky="ns")
            info = tf(r,"transparent"); info.grid(row=0,column=1,sticky="w",padx=12)
            nr = tf(info,"transparent"); nr.pack(anchor="w")
            tl(nr, prof["name"], FONT_HEAD, Colors.TXT).pack(side="left")
            if ia:
                p = tf(nr, Colors.ACC, corner_radius=10); p.pack(side="left",padx=(8,0))
                tl(p, "ACTIVE", FONT_SMALL, Colors.BG0).pack(padx=6,pady=1)
            tl(info, f"MC {prof['version']} • {prof.get('loader','vanilla').title()} • {prof.get('memory_mb',4096)} MB", Colors.MUT, FONT_SMALL).pack(anchor="w")
            btns = tf(r,"transparent"); btns.grid(row=0,column=2,padx=10)
            if not ia: tb(btns, "Activate", lambda p=prof: self._act(p), True, 90, 28).pack(pady=2)
            if len(self.app.store.profiles)>1: tb(btns, "Delete", lambda p=prof: self._del(p), False, 90, 28).pack(pady=2)
    
    def _act(self, prof):
        self.app.store.config["active_profile"]=prof["id"]; self.app.store.save(); self.refresh(); self.app.refresh_bar(); self.app.navigate_to("home")
    
    def _del(self, prof):
        if messagebox.askyesno("Delete Profile",f"Delete '{prof['name']}'?"):
            self.app.store.delete_profile(prof["id"]); self.refresh(); self.app.refresh_bar()
    
    def _cd(self):
        d = NewProfileDialog(self.app); self.app.wait_window(d); self.refresh()


class NewProfileDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app); self.app = app; self.title("New Profile"); self.geometry("420x340"); self.configure(fg_color=Colors.BG0); self.after(100, self.grab_set)
        tl(self, "Create New Profile", FONT_TITLE).pack(pady=(20,0))
        tl(self, "Set up a new game configuration", Colors.MUT, FONT_SMALL).pack()
        f = tf(self, Colors.BG1, corner_radius=10); f.pack(fill="both", expand=True, padx=20, pady=16)
        for label, var, vals in [("Name",ctk.StringVar(value="My Profile"),None),("Version",ctk.StringVar(value="26.1.2"),POPULAR_VERSIONS),("Loader",ctk.StringVar(value="vanilla"),LOADER_CHOICES)]:
            r = tf(f,"transparent"); r.pack(fill="x",padx=16,pady=6)
            tl(r, label, Colors.MUT, FONT_SMALL, width=80, anchor="w").pack(side="left")
            if vals: ctk.CTkComboBox(r,values=vals,variable=var,fg_color=Colors.BG2,text_color=Colors.TXT,button_color=Colors.AC3,dropdown_fg_color=Colors.BG1).pack(side="left",fill="x",expand=True)
            else: ctk.CTkEntry(r,textvariable=var,fg_color=Colors.BG2,text_color=Colors.TXT,border_color=Colors.AC3).pack(side="left",fill="x",expand=True)
        self._vars = [var for var,_,_ in [(ctk.StringVar(value="My Profile"),None,None),("",POPULAR_VERSIONS,None),("",LOADER_CHOICES,None)]]
        btns = tf(self,"transparent"); btns.pack(pady=(0,20))
        tb(btns, "Create", lambda: [self.app.store.create_profile(self._vars[0].get() or "New Profile",self._vars[1].get(),self._vars[2].get()), self.destroy()]).pack(side="left",padx=4)
        tb(btns, "Cancel", self.destroy, False).pack(side="left",padx=4)


class ModsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent"); self.app = app; self._build()
    
    def _build(self):
        h = tf(self,"transparent"); h.pack(fill="x",padx=20,pady=(20,0))
        tl(h, "Mod Manager", FONT_TITLE).pack(side="left")
        tb(h, "+ Add Mods", self._add, w=110).pack(side="right")
        tb(h, "Open Folder", self._of, False, w=110).pack(side="right",padx=(0,8))
        tl(self, "Mods are per-profile. Uses Fabric/Forge/Quilt.", Colors.MUT, FONT_SMALL).pack(padx=20,anchor="w",pady=(4,0))
        tf(self, height=1, fg_color=Colors.AC3, corner_radius=0).pack(fill="x",padx=20,pady=8)
        self._lf = ctk.CTkScrollableFrame(self, fg_color=Colors.BG1, corner_radius=10)
        self._lf.pack(fill="both", expand=True, padx=20, pady=(0,20)); self.refresh()
    
    def refresh(self):
        for w in self._lf.winfo_children(): w.destroy()
        folder = self.app.store.mods_dir(self.app.store.active_profile())
        mods = sorted(folder.glob("*.jar"))
        if not mods:
            tl(self._lf, "No mods installed.\nClick '+ Add Mods' to add .jar files.", Colors.MUT, FONT_SMALL).pack(expand=True,pady=40); return
        for jar in mods:
            r = tf(self._lf, Colors.BG2, corner_radius=8); r.pack(fill="x",padx=8,pady=4); r.grid_columnconfigure(1,weight=1)
            ic = tf(r, Colors.AC3, corner_radius=6); ic.grid(row=0,column=0,padx=(10,0),pady=8)
            tl(ic, "JAR", FONT_SMALL, Colors.ACC).pack(padx=6,pady=4)
            inf = tf(r,"transparent"); inf.grid(row=0,column=1,sticky="w",padx=10)
            tl(inf, jar.stem, FONT_HEAD, Colors.TXT).pack(anchor="w")
            tl(inf, f"{jar.stat().st_size//1024:,} KB", Colors.MUT, FONT_SMALL).pack(anchor="w")
            tb(r, "Remove", lambda p=jar: [p.unlink(missing_ok=True), self.refresh()], False, 80, 28).grid(row=0,column=2,padx=10)
    
    def _add(self):
        folder = self.app.store.mods_dir(self.app.store.active_profile())
        for f in filedialog.askopenfilenames(title="Select Mod JARs",filetypes=[("Minecraft Mods","*.jar"),("All Files","*.*")]):
            dst = folder/Path(f).name
            if not dst.exists(): shutil.copy2(f,dst)
        self.refresh()
    
    def _of(self): od(self.app.store.mods_dir(self.app.store.active_profile()))


class ShadersPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent"); self.app = app; self._build()
    
    def _build(self):
        h = tf(self,"transparent"); h.pack(fill="x",padx=20,pady=(20,0))
        tl(h, "Shader Manager", FONT_TITLE).pack(side="left")
        tb(h, "+ Add Shader", self._add, w=120).pack(side="right")
        tb(h, "Open Folder", self._of, False, w=110).pack(side="right",padx=(0,8))
        tl(self, "Shaders are per-profile. Requires OptiFine or Iris.", Colors.MUT, FONT_SMALL).pack(padx=20,anchor="w",pady=(4,0))
        tf(self, height=1, fg_color=Colors.AC3, corner_radius=0).pack(fill="x",padx=20,pady=8)
        self._lf = ctk.CTkScrollableFrame(self, fg_color=Colors.BG1, corner_radius=10)
        self._lf.pack(fill="both", expand=True, padx=20, pady=(0,20)); self.refresh()
    
    def refresh(self):
        for w in self._lf.winfo_children(): w.destroy()
        prof = self.app.store.active_profile(); folder = self.app.store.shaders_dir(prof)
        shaders = sorted([f for f in folder.iterdir() if f.suffix.lower() in (".zip",".7z")])
        if not shaders:
            tl(self._lf, "No shader packs installed.\nClick '+ Add Shader'.", Colors.MUT, FONT_SMALL).pack(expand=True,pady=40); return
        active = prof.get("active_shader","")
        for sp in shaders:
            ia = sp.name == active
            r = tf(self._lf, Colors.BG2, corner_radius=8); r.pack(fill="x",padx=8,pady=4); r.grid_columnconfigure(1,weight=1)
            co = Colors.GRN if ia else Colors.AC3
            ic = tf(r, co, corner_radius=6); ic.grid(row=0,column=0,padx=(10,0),pady=8)
            tl(ic, "SHD", FONT_SMALL, Colors.BG0 if ia else Colors.ACC).pack(padx=6,pady=4)
            inf = tf(r,"transparent"); inf.grid(row=0,column=1,sticky="w",padx=10)
            tl(inf, sp.stem, FONT_HEAD, Colors.TXT).pack(anchor="w")
            tl(inf, "ACTIVE" if ia else f"{sp.stat().st_size//1024:,} KB", Colors.GRN if ia else Colors.MUT, FONT_SMALL).pack(anchor="w")
            btns = tf(r,"transparent"); btns.grid(row=0,column=2,padx=10)
            if not ia: tb(btns, "Set Active", lambda p=sp: [prof.update({"active_shader":p.name}), self.app.store.save(), self.refresh()], True, 90, 28).pack(pady=2)
            tb(btns, "Remove", lambda p=sp: [prof.update({"active_shader":""}) if prof.get("active_shader")==p.name else None, p.unlink(missing_ok=True), self.app.store.save(), self.refresh()], False, 90, 28).pack(pady=2)
    
    def _add(self):
        folder = self.app.store.shaders_dir(self.app.store.active_profile())
        for f in filedialog.askopenfilenames(title="Select Shader Packs",filetypes=[("Shader Packs","*.zip *.7z"),("All Files","*.*")]):
            dst = folder/Path(f).name
            if not dst.exists(): shutil.copy2(f,dst)
        self.refresh()
    
    def _of(self): od(self.app.store.shaders_dir(self.app.store.active_profile()))


class ConsolePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent"); self.app = app; self._build()
    
    def _build(self):
        h = tf(self,"transparent"); h.pack(fill="x",padx=20,pady=(20,0))
        tl(h, "Console", FONT_TITLE).pack(side="left")
        btns = tf(h,"transparent"); btns.pack(side="right")
        tb(btns, "Clear", self._cl, False, 80).pack(side="left",padx=4)
        tb(btns, "Kill Game", self._kill, False, 90).pack(side="left")
        self._txt = ctk.CTkTextbox(self, fg_color=Colors.BG1, text_color=Colors.TXT, font=FONT_MONO, corner_radius=10, wrap="word", state="disabled")
        self._txt.pack(fill="both", expand=True, padx=20, pady=(0,20))
        self._poll()
    
    def _poll(self):
        try:
            while True:
                msg = self.app.log_queue.get_nowait()
                self._txt.configure(state="normal"); self._txt.insert("end",msg+"\n"); self._txt.see("end"); self._txt.configure(state="disabled")
        except Empty: pass
        self.after(100, self._poll)
    
    def _cl(self): self._txt.configure(state="normal"); self._txt.delete("1.0","end"); self._txt.configure(state="disabled")
    def _kill(self): self.app.minecraft.kill()


# ══════════════════════════════════════════════════════════
#  Main Application
# ══════════════════════════════════════════════════════════

class UltraWaterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.log = setup_logging()
        self.log_queue: Queue = Queue()
        self.store = DataStore(self.log)
        self.minecraft = MinecraftManager(self.store, self.log, self.log_queue)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry(WINDOW_SIZE)
        self.minsize(*MIN_SIZE)
        self.configure(fg_color=Colors.BG0)
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._nav_btns: Dict[str, ctk.CTkButton] = {}
        self._pages: Dict[str, ctk.CTkFrame] = {}
        
        self._build_sidebar()
        self._build_content()
        self._build_bar()
        self._load_pages()
        self.navigate_to("home")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _build_sidebar(self):
        sb = tf(self, Colors.BG1, corner_radius=0)
        sb.grid(row=0,column=0,sticky="nsew"); sb.grid_rowconfigure(10,weight=1)
        logo = tf(sb,"transparent"); logo.grid(row=0,column=0,pady=(20,16),padx=16,sticky="w")
        drop = tf(logo, Colors.ACC, corner_radius=50); drop.pack(side="left")
        tl(drop, "UW", ("Consolas",11,"bold"), Colors.BG0).pack(padx=7,pady=5)
        nc = tf(logo,"transparent"); nc.pack(side="left",padx=(8,0))
        tl(nc, "UltraWater", ("Consolas",13,"bold"), Colors.ACC).pack(anchor="w")
        tl(nc, f"v{VERSION}", FONT_SMALL, Colors.MUT).pack(anchor="w")
        ctk.CTkFrame(sb,height=1,fg_color=Colors.AC3,corner_radius=0).grid(row=1,column=0,sticky="ew",padx=12,pady=4)
        for i,(k,lbl) in enumerate([("home","⬡  Home"),("mods","⬢  Mods"),("shaders","◈  Shaders"),("profiles","◉  Profiles"),("settings","⚙  Settings"),("console","⌨  Console")]):
            btn = ctk.CTkButton(sb,text=lbl,font=FONT_BODY,anchor="w",fg_color="transparent",hover_color=Colors.BG3,text_color=Colors.MUT,corner_radius=8,height=38,command=lambda k=k: self.navigate_to(k))
            btn.grid(row=i+2,column=0,sticky="ew",padx=10,pady=2); self._nav_btns[k]=btn
        foot = tf(sb,"transparent"); foot.grid(row=11,column=0,sticky="ew",padx=12,pady=12)
        tl(foot, "ultrawater.gg", Colors.AC3, FONT_SMALL).pack(anchor="w")
        tl(foot, "Free. Always.", Colors.AC3, FONT_SMALL).pack(anchor="w")
    
    def _build_content(self):
        self._cont = tf(self, Colors.BG0, corner_radius=0)
        self._cont.grid(row=0,column=1,sticky="nsew")
        self._cont.grid_rowconfigure(0,weight=1); self._cont.grid_columnconfigure(0,weight=1)
    
    def _build_bar(self):
        bar = tf(self, Colors.BG1, corner_radius=0)
        bar.grid(row=1,column=0,columnspan=2,sticky="ew"); bar.grid_columnconfigure(2,weight=1)
        tl(bar, "Profile:", Colors.MUT, FONT_SMALL).grid(row=0,column=0,padx=(16,4),pady=10)
        names = [p["name"] for p in self.store.profiles]
        self._pv = ctk.StringVar(value=self.store.active_profile().get("name","Default"))
        self._pm = ctk.CTkComboBox(bar,values=names,variable=self._pv,command=lambda n: [self.store.config.update({"active_profile":next(p["id"] for p in self.store.profiles if p["name"]==n)}),self.store.save(),self._vv.set(next(p.get("version","26.1.2") for p in self.store.profiles if p["name"]==n)),self._lv.set(next(p.get("loader","vanilla") for p in self.store.profiles if p["name"]==n))],fg_color=Colors.BG2,text_color=Colors.TXT,button_color=Colors.AC3,dropdown_fg_color=Colors.BG1,width=140,font=FONT_BODY)
        self._pm.grid(row=0,column=1,padx=(0,12),pady=10)
        prof = self.store.active_profile()
        tl(bar, "Version:", Colors.MUT, FONT_SMALL).grid(row=0,column=2,padx=(0,4),sticky="e")
        self._vv = ctk.StringVar(value=prof.get("version","26.1.2"))
        ctk.CTkComboBox(bar,values=POPULAR_VERSIONS,variable=self._vv,command=lambda v: [self.store.active_profile().update({"version":v}),self.store.save()],fg_color=Colors.BG2,text_color=Colors.TXT,button_color=Colors.AC3,dropdown_fg_color=Colors.BG1,width=120,font=FONT_BODY).grid(row=0,column=3,padx=(0,8),pady=10)
        tl(bar, "Loader:", Colors.MUT, FONT_SMALL).grid(row=0,column=4,padx=(0,4))
        self._lv = ctk.StringVar(value=prof.get("loader","vanilla"))
        ctk.CTkComboBox(bar,values=LOADER_CHOICES,variable=self._lv,command=lambda l: [self.store.active_profile().update({"loader":l}),self.store.save()],fg_color=Colors.BG2,text_color=Colors.TXT,button_color=Colors.AC3,dropdown_fg_color=Colors.BG1,width=100,font=FONT_BODY).grid(row=0,column=5,padx=(0,16),pady=10)
        self._lb = ctk.CTkButton(bar,text="▶  LAUNCH",font=("Consolas",14,"bold"),fg_color=Colors.ACC,hover_color=Colors.AC2,text_color=Colors.BG0,corner_radius=8,width=160,height=42,command=self._toggle_launch)
        self._lb.grid(row=0,column=6,padx=(0,16),pady=8)
        self._sv = ctk.StringVar(value="Ready")
        self._sl = tl(bar, "", Colors.MUT, FONT_SMALL); self._sl.configure(textvariable=self._sv); self._sl.grid(row=0,column=7,padx=8)
    
    def _load_pages(self):
        self._pages = {"home":HomePage(self._cont,self),"mods":ModsPage(self._cont,self),"shaders":ShadersPage(self._cont,self),"profiles":ProfilesPage(self._cont,self),"settings":SettingsPage(self._cont,self),"console":ConsolePage(self._cont,self)}
    
    def navigate_to(self, key):
        for p in self._pages.values(): p.grid_forget()
        page = self._pages.get(key)
        if page: page.grid(row=0,column=0,sticky="nsew")
        if page and hasattr(page,"refresh"): page.refresh()
        for k,btn in self._nav_btns.items():
            btn.configure(fg_color=Colors.BG3 if k==key else "transparent", text_color=Colors.TXT if k==key else Colors.MUT)
    
    def refresh_bar(self):
        names = [p["name"] for p in self.store.profiles]
        self._pm.configure(values=names)
        active = self.store.active_profile()
        self._pv.set(active.get("name","Default")); self._vv.set(active.get("version","26.1.2")); self._lv.set(active.get("loader","vanilla"))
    
    def _toggle_launch(self):
        if self.minecraft.is_running:
            self.minecraft.kill(); self._lb.configure(text="▶  LAUNCH",fg_color=Colors.ACC); self._sv.set("Stopped."); return
        prof = self.store.active_profile()
        prof["version"]=self._vv.get(); prof["loader"]=self._lv.get(); self.store.save()
        self._lb.configure(text="■  STOP",fg_color="#aa2222"); self._sv.set("Launching..."); self.navigate_to("console")
        def t():
            try: self.minecraft.launch(prof)
            except: pass
            finally: self.after(0,lambda: [self._lb.configure(text="▶  LAUNCH",fg_color=Colors.ACC), self._sv.set("Game exited.")])
        threading.Thread(target=t,daemon=True).start()
        if self.store.config.get("close_on_launch",False): self.withdraw()
    
    def _on_close(self):
        if self.minecraft.is_running:
            if messagebox.askyesno("Quit?","Minecraft is running. Kill it and exit?"): self.minecraft.kill()
            else: return
        self.store.save(); self.destroy()


# ══════════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════════

def main():
    try:
        import customtkinter as ctk
    except ImportError:
        print("✗ customtkinter not installed.\n  Run: pip install customtkinter")
        sys.exit(1)
    
    if not HAS_MCLIB:
        print("⚠ minecraft_launcher_lib not installed.\n  Run: pip install minecraft-launcher-lib>=8.0\n  Launcher will start but cannot install/launch Minecraft.")
    
    # Run setup wizard completely independently to prevent Tkinter window freezing
    if HAS_WIZARD and is_first_run():
        temp_root = ctk.CTk()
        temp_root.withdraw()
        state = run_setup_wizard(temp_root)
        temp_root.destroy()
        if not state.completed:
            sys.exit(0)
    
    app = UltraWaterApp()
    app.mainloop()

if __name__ == "__main__":
    main()