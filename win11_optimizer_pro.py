"""
Windows 11 Optimizer & Productivity Suite Pro
A comprehensive system optimization and maintenance tool with modern GUI

Author: avraniel
Version: 2.0 (Fixed & Consolidated)
Date: 2026-03-03
"""

import tkinter
from tkinter import messagebox
import customtkinter as ctk
import os
import subprocess
import shutil
import ctypes
import threading
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Callable, List, Dict, Any

# --- Library Check ---
try:
    import psutil
except ImportError:
    print("ERROR: 'psutil' library not found.")
    print("Please run: pip install psutil")
    sys.exit()

# --- Settings for the Modern GUI ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class Logger:
    """Centralized logging system"""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or str(Path.home() / "Win11Optimizer_Logs" / "optimizer.log")
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        self.callbacks = []
        
        # Setup file logging
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def add_callback(self, callback: Callable[[str], None]):
        """Add callback for log messages (e.g., GUI update)"""
        self.callbacks.append(callback)
    
    def info(self, message: str):
        """Log info message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        logging.info(message)
        for callback in self.callbacks:
            try:
                callback(log_entry)
            except Exception:
                pass


class OptimizationEngine:
    """Separate logic from UI for better maintainability"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.undo_stack: List[Dict[str, Any]] = []
        self.backup_dir = Path.home() / "Win11Optimizer_Backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.is_admin = self.check_admin()
        
    def check_admin(self) -> bool:
        """Check if running with admin privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception as e:
            self.logger.info(f"❌ Admin check failed: {e}")
            return False
    
    def log(self, message: str):
        """Log message through logger"""
        self.logger.info(message)
    
    def run_elevated_command(
        self,
        cmd,
        use_shell: bool = False,
        timeout: int = 30
    ) -> Tuple[bool, Optional[subprocess.CompletedProcess]]:
        """Run command with proper error handling and timeout"""
        
        if not self.is_admin:
            self.log("❌ Admin privileges required for this operation")
            return False, None
        
        try:
            if use_shell and isinstance(cmd, list):
                cmd = " ".join(cmd)
            
            result = subprocess.run(
                cmd,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0 and result.stderr:
                self.log(f"   ⚠️ Warning: {result.stderr[:150]}")
            return result.returncode == 0, result
            
        except subprocess.TimeoutExpired:
            self.log(f"   ❌ Command timed out after {timeout}s")
            return False, None
        except Exception as e:
            self.log(f"   ❌ Error: {str(e)}")
            return False, None
    
    def backup_registry_key(self, key_path: str, description: str) -> Optional[str]:
        """Export registry key before modification"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_desc = "".join(
                c for c in description if c.isalnum() or c in (' ', '-', '_')
            ).rstrip()
            backup_file = self.backup_dir / f"{safe_desc}_{timestamp}.reg"
            
            success, _ = self.run_elevated_command(
                ["reg", "export", key_path, str(backup_file), "/y"],
                use_shell=False
            )
            
            if success:
                self.log(f"   💾 Backup created: {backup_file.name}")
                return str(backup_file)
            else:
                self.log(f"   ⚠️ Backup failed for {key_path}")
                return None
                
        except Exception as e:
            self.log(f"   ❌ Backup error: {e}")
            return None
    
    def safe_reg_add(
        self,
        key: str,
        value_name: Optional[str] = None,
        value_data: Optional[str] = None,
        value_type: str = "REG_SZ",
        backup_desc: Optional[str] = None
    ) -> bool:
        """Safe registry modification with backup"""
        try:
            if backup_desc:
                self.backup_registry_key(key, backup_desc)
            
            cmd = ["reg", "add", key, "/f"]
            
            if value_name:
                cmd.extend(["/v", value_name])
            if value_data is not None:
                cmd.extend(["/d", str(value_data)])
            if value_type:
                cmd.extend(["/t", value_type])
            
            success, _ = self.run_elevated_command(cmd, use_shell=False)
            return success
            
        except Exception as e:
            self.log(f"   ❌ Registry modification error: {e}")
            return False
    
    def safe_reg_delete(self, key: str, value_name: Optional[str] = None) -> bool:
        """Safely delete registry key or value"""
        try:
            cmd = ["reg", "delete", key, "/f"]
            
            if value_name:
                cmd.extend(["/v", value_name])
            
            success, _ = self.run_elevated_command(cmd, use_shell=False)
            return success
            
        except Exception as e:
            self.log(f"   ❌ Registry deletion error: {e}")
            return False
    
    def check_winget(self) -> bool:
        """Verify winget is available"""
        success, _ = self.run_elevated_command(["winget", "--version"], timeout=10)
        return success
    
    def clean_directory(self, path: str) -> Tuple[int, int]:
        """Safely clean temporary directories - returns (cleaned, errors)"""
        if not path or not os.path.exists(path):
            return 0, 0
        
        count = 0
        errors = 0
        
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                        count += 1
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                        count += 1
                except PermissionError:
                    errors += 1
                except Exception as e:
                    self.log(f"   ⚠️ Could not clean {item}: {e}")
                    errors += 1
        except Exception as e:
            self.log(f"   ⚠️ Error accessing {path}: {e}")
        
        if errors > 0:
            self.log(f"   ⚠️ Could not remove {errors} items (in use)")
        
        return count, errors
    
    def create_restore_point(self) -> bool:
        """Create system restore point with proper error handling"""
        self.log("🛡️ Creating System Restore Point...")
        
        try:
            # Enable system restore on C: first
            self.run_elevated_command([
                "powershell", "-ExecutionPolicy", "Bypass", "-Command",
                "Enable-ComputerRestore -Drive 'C:\\' -ErrorAction SilentlyContinue"
            ], timeout=60)
            
            # Create checkpoint
            success, result = self.run_elevated_command([
                "powershell", "-ExecutionPolicy", "Bypass", "-Command",
                "Checkpoint-Computer -Description 'Win11Optimizer_Backup' "
                "-RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop"
            ], timeout=120)
            
            if success:
                self.log("   ✔️ Restore point created successfully")
                self.undo_stack.append({
                    "action": "restore_point",
                    "description": "System restore point created"
                })
            else:
                self.log("   ⚠️ Restore point creation may have failed")
            
            return success
            
        except Exception as e:
            self.log(f"   ❌ Error creating restore point: {e}")
            return False
    
    def fix_context_menu(self) -> bool:
        """Restore old Windows 10 right-click menu"""
        self.log("🖱️ Restoring Old Context Menu...")
        
        try:
            key = r"HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
            parent_key = r"HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
            
            backup = self.backup_registry_key(parent_key, "Context_Menu_Backup")
            
            # Delete the InprocServer32 key to restore old menu
            success = self.safe_reg_delete(key)
            
            if success:
                self.log("   ✔️ Registry updated. Restart Explorer or sign out to apply.")
                self.undo_stack.append({
                    "action": "context_menu",
                    "backup_file": backup,
                    "description": "Context menu restoration"
                })
            
            return success
            
        except Exception as e:
            self.log(f"   ❌ Context menu fix error: {e}")
            return False
    
    def disable_animations(self) -> bool:
        """Disable visual animations for performance"""
        self.log("💨 Disabling Visual Animations...")
        
        try:
            key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
            backup = self.backup_registry_key(key, "Visual_Effects_Backup")
            
            success = self.safe_reg_add(
                key,
                "VisualFXSetting",
                "2",
                "REG_DWORD",
                backup_desc="VisualFX"
            )
            
            if success:
                self.log("   ✔️ Animations disabled. Sign out/in to apply changes.")
                self.undo_stack.append({
                    "action": "disable_animations",
                    "backup_file": backup,
                    "description": "Visual effects restoration"
                })
            
            return success
            
        except Exception as e:
            self.log(f"   ❌ Animation disable error: {e}")
            return False
    
    def disable_transparency(self) -> bool:
        """Disable transparency effects to reduce GPU load"""
        self.log("🔍 Disabling Transparency Effects...")
        
        try:
            key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            backup = self.backup_registry_key(key, "Transparency_Backup")
            
            success = self.safe_reg_add(
                key,
                "EnableTransparency",
                "0",
                "REG_DWORD",
                backup_desc="Transparency"
            )
            
            if success:
                self.log("   ✔️ Transparency effects disabled.")
                self.undo_stack.append({
                    "action": "disable_transparency",
                    "backup_file": backup,
                    "description": "Transparency effects restoration"
                })
            
            return success
            
        except Exception as e:
            self.log(f"   ❌ Transparency disable error: {e}")
            return False
    
    def remove_bloatware(self) -> int:
        """Remove specific bloatware apps"""
        self.log("🗑️ Removing bloatware...")
        
        bloat = [
            ("Microsoft.549981C3F5F10", "Cortana"),
            ("Microsoft.WindowsMaps", "Maps"),
            ("Microsoft.ZuneMusic", "Groove Music"),
            ("Microsoft.ZuneVideo", "Movies & TV"),
            ("Microsoft.BingWeather", "Weather"),
            ("Microsoft.GetHelp", "Get Help"),
            ("Microsoft.MixedReality.Portal", "Mixed Reality Portal"),
            ("Microsoft.OneDrive", "OneDrive (optional)"),
        ]
        
        removed = []
        
        try:
            for app_id, name in bloat:
                self.log(f"   Removing {name}...")
                success, _ = self.run_elevated_command([
                    "powershell", "-ExecutionPolicy", "Bypass", "-Command",
                    f"Get-AppxPackage '*{app_id}*' -AllUsers | "
                    f"Remove-AppxPackage -ErrorAction SilentlyContinue"
                ], timeout=60)
                
                if success:
                    removed.append(app_id)
                    self.log(f"   ✔️ Removed {name}")
            
            self.log(f"   ✔️ Removed {len(removed)} applications")
            
            if removed:
                self.undo_stack.append({
                    "action": "remove_bloatware",
                    "removed_apps": removed,
                    "description": "Bloatware removal"
                })
            
            return len(removed)
            
        except Exception as e:
            self.log(f"   ❌ Bloatware removal error: {e}")
            return len(removed)
    
    def install_tools(self) -> List[str]:
        """Install productivity tools via winget"""
        self.log("📦 Installing Productivity Tools...")
        
        if not self.check_winget():
            self.log("   ❌ Winget not available. Install App Installer from Microsoft Store.")
            return []
        
        tools = [
            ("Microsoft.PowerToys", "PowerToys"),
            ("voidtools.Everything", "Everything Search"),
            ("Flow-Launcher.Flow.Launcher", "Flow Launcher"),
            ("7zip.7zip", "7-Zip"),
        ]
        
        installed = []
        
        try:
            for tool_id, name in tools:
                self.log(f"   Installing {name}...")
                success, _ = self.run_elevated_command([
                    "winget", "install", "--id", tool_id, "-e", "--silent",
                    "--accept-package-agreements", "--accept-source-agreements"
                ], timeout=300)
                
                if success:
                    self.log(f"   ✔️ {name} installed")
                    installed.append(name)
                else:
                    self.log(f"   ⚠️ {name} may already be installed or failed")
            
            return installed
            
        except Exception as e:
            self.log(f"   ❌ Tool installation error: {e}")
            return installed
    
    def set_high_performance_power(self) -> bool:
        """Set high performance power plan safely"""
        self.log("⚡ Configuring Power Settings...")
        
        try:
            high_perf_guid = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
            
            # Get available schemes
            success, result = self.run_elevated_command(["powercfg", "/list"])
            if not success or not result:
                self.log("   ⚠️ Could not retrieve power schemes")
                return False
            
            # Check if High Performance exists
            if high_perf_guid in result.stdout:
                success, _ = self.run_elevated_command(
                    ["powercfg", "/setactive", high_perf_guid]
                )
                if success:
                    self.log("   ✔️ High Performance mode activated")
                    self.undo_stack.append({
                        "action": "power_plan",
                        "description": "Power plan change"
                    })
                    return True
            else:
                # Try to create it
                self.log("   Creating High Performance power plan...")
                self.run_elevated_command(
                    ["powercfg", "-duplicatescheme", high_perf_guid]
                )
                success, _ = self.run_elevated_command(
                    ["powercfg", "/setactive", high_perf_guid]
                )
                if success:
                    self.log("   ✔️ High Performance mode activated")
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"   ❌ Power settings error: {e}")
            return False
    
    def run_full_optimization(self, progress_callback: Optional[Callable] = None) -> bool:
        """Execute full optimization routine"""
        self.log("\n" + "="*60)
        self.log("🚀 STARTING FULL SYSTEM OPTIMIZATION")
        self.log("="*60)
        
        steps = [
            ("Cleaning Temp Files", self._clean_temp),
            ("Flushing DNS Cache", self._flush_dns),
            ("Cleaning Update Cache", self._clean_update_cache),
            ("Disabling Telemetry", self._disable_telemetry),
            ("Disabling SysMain", self._disable_sysmain),
            ("Setting Power Plan", self.set_high_performance_power),
        ]
        
        try:
            for i, (name, func) in enumerate(steps, 1):
                if progress_callback:
                    progress_callback(i, len(steps), name)
                
                self.log(f"\n[{i}/{len(steps)}] {name}...")
                
                try:
                    func()
                except Exception as e:
                    self.log(f"   ⚠️ Error in {name}: {e}")
            
            self.log("\n" + "="*60)
            self.log("✅ OPTIMIZATION COMPLETE!")
            self.log("="*60 + "\n")
            return True
            
        except Exception as e:
            self.log(f"\n❌ Optimization failed: {e}\n")
            return False
    
    def _clean_temp(self):
        """Step 1: Clean temporary files"""
        temp_paths = [
            os.getenv('TEMP'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Temp')
        ]
        
        total = 0
        for path in temp_paths:
            if path:
                count, errors = self.clean_directory(path)
                total += count
                self.log(f"   Cleaned {count} items in {path}")
    
    def _flush_dns(self):
        """Step 2: Flush DNS cache"""
        success, _ = self.run_elevated_command(["ipconfig", "/flushdns"])
        if success:
            self.log("   ✔️ DNS cache flushed")
    
    def _clean_update_cache(self):
        """Step 3: Clean Windows Update cache"""
        try:
            self.run_elevated_command(["net", "stop", "wuauserv"], timeout=30)
            update_path = os.path.join(
                os.environ.get('WINDIR', 'C:\\Windows'),
                'SoftwareDistribution',
                'Download'
            )
            count, _ = self.clean_directory(update_path)
            self.log(f"   Cleaned {count} update cache files")
            self.run_elevated_command(["net", "start", "wuauserv"], timeout=30)
        except Exception as e:
            self.log(f"   ⚠️ Update cache cleaning error: {e}")
    
    def _disable_telemetry(self):
        """Step 4: Disable telemetry services"""
        try:
            self.run_elevated_command(
                ["sc", "config", "DiagTrack", "start=disabled"],
                use_shell=False
            )
            self.run_elevated_command(
                ["sc", "stop", "DiagTrack"],
                use_shell=False
            )
            self.log("   ✔️ Telemetry disabled")
            self.undo_stack.append({
                "action": "disable_telemetry",
                "description": "Telemetry service configuration"
            })
        except Exception as e:
            self.log(f"   ⚠️ Telemetry disable error: {e}")
    
    def _disable_sysmain(self):
        """Step 5: Disable SysMain (Superfetch)"""
        try:
            self.run_elevated_command(
                ["sc", "config", "SysMain", "start=disabled"],
                use_shell=False
            )
            self.run_elevated_command(
                ["sc", "stop", "SysMain"],
                use_shell=False
            )
            self.log("   ✔️ SysMain disabled")
            self.undo_stack.append({
                "action": "disable_sysmain",
                "description": "SysMain service configuration"
            })
        except Exception as e:
            self.log(f"   ⚠️ SysMain disable error: {e}")


class Win11OptimizerPro(ctk.CTk):
    """Main GUI Application"""
    
    def __init__(self):
        super().__init__()
        
        # Window Configuration
        self.title("Windows 11 Optimizer & Productivity Suite Pro")
        self.geometry("1000x800")
        self.resizable(False, False)
        self.eval('tk::PlaceWindow . center')
        
        # Initialize Logger
        self.logger = Logger()
        
        # Initialize Engine
        self.engine = OptimizationEngine(self.logger)
        self.logger.add_callback(self.log)
        
        # Admin Check
        self.is_admin = self.engine.is_admin
        
        # Build GUI
        self.create_gui()
        
        # Start Hardware Monitoring
        self.update_stats()
        
        # Show admin warning if needed
        if not self.is_admin:
            messagebox.showwarning(
                "Admin Required",
                "This application requires administrator privileges.\n\n"
                "Please restart it as Administrator for full functionality."
            )

    def create_gui(self):
        """Create the main GUI layout"""
        # Main Container
        self.frame = ctk.CTkFrame(self, corner_radius=0)
        self.frame.pack(fill="both", expand=True, padx=20, pady=20)

        # --- Top Frame: Header & Live Stats ---
        self.top_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.top_frame.pack(fill="x", pady=(0, 10))

        self.title_label = ctk.CTkLabel(
            self.top_frame,
            text="🚀 Windows 11 Optimizer Pro",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(side="left")

        # Live Stats Frame
        self.stats_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.stats_frame.pack(side="right")
        
        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="CPU: 0%  |  RAM: 0%",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#00FF00"
        )
        self.stats_label.pack(side="right", padx=10)

        # Admin Warning
        admin_status = "✅ Admin Active" if self.is_admin else "⚠️ Admin Required (Restart as Admin)"
        color = "#00FF00" if self.is_admin else "#FFCC00"
        self.admin_label = ctk.CTkLabel(
            self.frame,
            text=admin_status,
            text_color=color,
            font=ctk.CTkFont(size=12)
        )
        self.admin_label.pack(pady=5)

        # --- Tab View ---
        self.tabview = ctk.CTkTabview(self.frame, width=960, height=600)
        self.tabview.pack(pady=5, fill="both", expand=True)
        
        self.tab_optimize = self.tabview.add("🛠️ Optimization")
        self.tab_tweaks = self.tabview.add("⚡ Productivity Tweaks")
        self.tab_safety = self.tabview.add("🛡️ Safety & Backup")
        self.tab_logs = self.tabview.add("📋 Logs")

        # Populate Tabs
        self.setup_optimization_tab()
        self.setup_tweaks_tab()
        self.setup_safety_tab()
        self.setup_logs_tab()

    def setup_optimization_tab(self):
        """Setup the optimization tab"""
        # Progress Frame
        self.progress_frame = ctk.CTkFrame(self.tab_optimize, fg_color="transparent")
        self.progress_frame.pack(pady=10, padx=10, fill="x")
        
        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.progress_label.pack()
        
        self.progress_bar = ctk.CTkProgressBar(self.tab_optimize, width=600, mode="determinate")
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)

        # Log Text
        self.log_text = ctk.CTkTextbox(
            self.tab_optimize,
            height=350,
            corner_radius=8,
            font=("Consolas", 10)
        )
        self.log_text.pack(pady=10, padx=10, fill="both", expand=True)

        # Control Buttons Frame
        btn_frame = ctk.CTkFrame(self.tab_optimize, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.btn_optimize = ctk.CTkButton(
            btn_frame,
            text="🚀 RUN FULL OPTIMIZATION",
            command=self.confirm_optimization,
            height=45,
            width=250,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_optimize.pack(side="left", padx=5)
        
        self.btn_undo = ctk.CTkButton(
            btn_frame,
            text="↩️ Undo Last Change",
            command=self.undo_last_action,
            height=45,
            width=180,
            fg_color="#D9534F",
            hover_color="#C9302C"
        )
        self.btn_undo.pack(side="left", padx=5)

    def setup_tweaks_tab(self):
        """Setup the productivity tweaks tab"""
        label = ctk.CTkLabel(
            self.tab_tweaks,
            text="One-Click System Tweaks",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        label.pack(pady=15)

        tweaks = [
            ("🖱️ Restore Old Right-Click Menu", self.engine.fix_context_menu, 
             "Brings back Windows 10 style context menu"),
            ("🗑️ Debloat: Remove Cortana & Apps", self.engine.remove_bloatware, 
             "Removes unnecessary pre-installed apps"),
            ("💨 Disable Animations (Speed UI)", self.engine.disable_animations, 
             "Turns off visual effects for better performance"),
            ("🔍 Disable Transparency Effects", self.engine.disable_transparency, 
             "Reduces GPU load by disabling acrylic effects")
        ]
        
        for text, command, tooltip in tweaks:
            btn = ctk.CTkButton(
                self.tab_tweaks,
                text=text,
                command=lambda c=command: self.run_tweak(c),
                height=45,
                font=ctk.CTkFont(size=13)
            )
            btn.pack(pady=8, padx=30, fill="x")
            
            # Tooltip label
            tip = ctk.CTkLabel(
                self.tab_tweaks,
                text=tooltip,
                text_color="gray",
                font=ctk.CTkFont(size=10)
            )
            tip.pack(pady=(0, 5))

        # Install Tools Section
        separator = ctk.CTkFrame(self.tab_tweaks, height=2, fg_color="gray")
        separator.pack(pady=20, padx=30, fill="x")
        
        install_label = ctk.CTkLabel(
            self.tab_tweaks,
            text="Install Productivity Tools",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        install_label.pack(pady=10)

        self.btn_install_tools = ctk.CTkButton(
            self.tab_tweaks,
            text="📦 Install PowerToys, Everything & Flow",
            fg_color="#2E8B57",
            hover_color="#206840",
            command=self.install_tools_thread,
            height=50,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_install_tools.pack(pady=10, padx=30, fill="x")

    def setup_safety_tab(self):
        """Setup the safety and backup tab"""
        label = ctk.CTkLabel(
            self.tab_safety,
            text="Safety & Recovery Center",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        label.pack(pady=15)

        # Restore Point
        self.btn_restore = ctk.CTkButton(
            self.tab_safety,
            text="🛡️ Create System Restore Point",
            command=self.create_restore_point_thread,
            height=50,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_restore.pack(pady=10, padx=30, fill="x")
        
        # Backup Registry
        self.btn_backup_reg = ctk.CTkButton(
            self.tab_safety,
            text="💾 Backup Current Registry",
            command=self.backup_full_registry,
            height=45,
            font=ctk.CTkFont(size=13)
        )
        self.btn_backup_reg.pack(pady=8, padx=30, fill="x")

        # System Info
        info_frame = ctk.CTkFrame(self.tab_safety, corner_radius=8)
        info_frame.pack(pady=20, padx=30, fill="both", expand=True)
        
        info_text = ctk.CTkTextbox(info_frame, font=("Consolas", 10))
        info_text.pack(padx=10, pady=10, fill="both", expand=True)
        
        try:
            win_version = sys.getwindowsversion()
            version_str = f"{win_version.major}.{win_version.minor}"
        except Exception:
            version_str = "Unknown"
        
        sys_info = f"""System Information:
{'='*50}
OS: {os.name}
Platform: {sys.platform}
Windows Version: {version_str}
Admin Privileges: {self.is_admin}
Backup Location: {self.engine.backup_dir}
Winget Available: {self.engine.check_winget()}
Log File: {self.logger.log_file}
{'='*50}
"""
        info_text.insert("1.0", sys_info)
        info_text.configure(state="disabled")

        self.info_label = ctk.CTkLabel(
            self.tab_safety,
            text="⚠️ Always create a restore point before making system changes!",
            text_color="#FFCC00",
            font=ctk.CTkFont(size=11)
        )
        self.info_label.pack(pady=5)

    def setup_logs_tab(self):
        """Setup the logs tab"""
        label = ctk.CTkLabel(
            self.tab_logs,
            text="Application Logs",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        label.pack(pady=15)

        # Logs textbox
        self.logs_text = ctk.CTkTextbox(
            self.tab_logs,
            corner_radius=8,
            font=("Consolas", 10)
        )
        self.logs_text.pack(pady=10, padx=10, fill="both", expand=True)

        # Buttons
        btn_frame = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        btn_frame.pack(pady=10)

        clear_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Clear Logs",
            command=self.clear_logs,
            height=40,
            width=150
        )
        clear_btn.pack(side="left", padx=5)

        open_btn = ctk.CTkButton(
            btn_frame,
            text="📂 Open Log File",
            command=self.open_log_file,
            height=40,
            width=150
        )
        open_btn.pack(side="left", padx=5)

    def log(self, message: str):
        """Add message to all log displays"""
        try:
            if hasattr(self, 'log_text'):
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
            
            if hasattr(self, 'logs_text'):
                self.logs_text.insert("end", message + "\n")
                self.logs_text.see("end")
        except Exception:
            pass

    def update_stats(self):
        """Update CPU and RAM stats"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            ram_percent = psutil.virtual_memory().percent
            
            self.stats_label.configure(
                text=f"CPU: {cpu_percent:.1f}%  |  RAM: {ram_percent:.1f}%"
            )
        except Exception as e:
            self.logger.info(f"Stats update error: {e}")
        
        # Schedule next update
        self.after(3000, self.update_stats)

    def update_progress(self, current: int, total: int, step_name: str):
        """Update progress bar and label"""
        try:
            progress = current / total
            self.progress_bar.set(progress)
            self.progress_label.configure(
                text=f"{step_name}... ({current}/{total})"
            )
            self.update()
        except Exception:
            pass

    def confirm_optimization(self):
        """Ask user for confirmation before running optimization"""
        if not self.is_admin:
            messagebox.showerror(
                "Admin Required",
                "Admin privileges are required to run optimization."
            )
            return
        
        response = messagebox.askyesno(
            "Confirm Optimization",
            "This will modify system settings and clean temporary files.\n\n"
            "We STRONGLY recommend creating a restore point first.\n\n"
            "Continue?"
        )
        
        if response:
            self.run_optimization_thread()

    def run_optimization_thread(self):
        """Run optimization in separate thread"""
        self.btn_optimize.configure(state="disabled")
        self.progress_label.configure(text="Running optimization...")
        
        thread = threading.Thread(
            target=self._optimization_worker,
            daemon=True
        )
        thread.start()

    def _optimization_worker(self):
        """Worker thread for optimization"""
        try:
            self.engine.run_full_optimization(
                progress_callback=self.update_progress
            )
        except Exception as e:
            self.logger.info(f"Optimization error: {e}")
        finally:
            self.btn_optimize.configure(state="normal")

    def run_tweak(self, command: Callable):
        """Run a single tweak in separate thread"""
        if not self.is_admin:
            messagebox.showerror(
                "Admin Required",
                "Admin privileges are required for system tweaks."
            )
            return
        
        thread = threading.Thread(
            target=command,
            daemon=True
        )
        thread.start()

    def install_tools_thread(self):
        """Install tools in separate thread"""
        if not self.is_admin:
            messagebox.showerror(
                "Admin Required",
                "Admin privileges are required to install tools."
            )
            return
        
        thread = threading.Thread(
            target=self._install_tools_worker,
            daemon=True
        )
        thread.start()

    def _install_tools_worker(self):
        """Worker for tool installation"""
        installed = self.engine.install_tools()
        if installed:
            messagebox.showinfo(
                "Installation Complete",
                f"Successfully installed:\n\n" + "\n".join(f"✔️ {tool}" for tool in installed)
            )
        else:
            messagebox.showwarning(
                "Installation Failed",
                "No tools were installed. Check logs for details."
            )

    def create_restore_point_thread(self):
        """Create restore point in separate thread"""
        if not self.is_admin:
            messagebox.showerror(
                "Admin Required",
                "Admin privileges are required to create restore points."
            )
            return
        
        thread = threading.Thread(
            target=self._restore_point_worker,
            daemon=True
        )
        thread.start()

    def _restore_point_worker(self):
        """Worker for restore point creation"""
        success = self.engine.create_restore_point()
        if success:
            messagebox.showinfo(
                "Success",
                "System restore point created successfully!"
            )
        else:
            messagebox.showwarning(
                "Warning",
                "Restore point creation may have failed. Check logs for details."
            )

    def backup_full_registry(self):
        """Create full registry backup"""
        if not self.is_admin:
            messagebox.showerror(
                "Admin Required",
                "Admin privileges are required for registry backup."
            )
            return
        
        thread = threading.Thread(
            target=self._backup_registry_worker,
            daemon=True
        )
        thread.start()

    def _backup_registry_worker(self):
        """Worker for registry backup"""
        self.logger.info("💾 Creating full registry backup...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.engine.backup_dir / f"FULL_REGISTRY_{timestamp}.reg"
        
        success, _ = self.engine.run_elevated_command([
            "reg", "export", "HKEY_LOCAL_MACHINE", str(backup_file), "/y"
        ])
        
        if success:
            self.logger.info(f"   ✔️ Registry backed up to: {backup_file.name}")
            messagebox.showinfo(
                "Success",
                f"Registry backed up successfully to:\n{backup_file}"
            )
        else:
            self.logger.info("   ❌ Registry backup failed")
            messagebox.showerror(
                "Error",
                "Registry backup failed. Check logs for details."
            )

    def undo_last_action(self):
        """Undo the last modification"""
        if not self.engine.undo_stack:
            messagebox.showinfo(
                "No Actions",
                "No previous actions to undo."
            )
            return
        
        action = self.engine.undo_stack.pop()
        self.logger.info(f"↩️ Undoing: {action['description']}")
        
        if 'backup_file' in action and action['backup_file']:
            response = messagebox.askyesno(
                "Undo Action",
                f"Restore from backup?\n{action['description']}\n\n"
                f"Backup: {action['backup_file']}"
            )
            
            if response:
                thread = threading.Thread(
                    target=self._restore_registry,
                    args=(action['backup_file'],),
                    daemon=True
                )
                thread.start()
        else:
            messagebox.showinfo(
                "Undo",
                f"Undo: {action['description']}\n\n"
                "Note: Some actions may require manual restoration."
            )

    def _restore_registry(self, backup_file: str):
        """Restore registry from backup file"""
        try:
            self.logger.info(f"Restoring from: {backup_file}")
            success, _ = self.engine.run_elevated_command([
                "reg", "import", backup_file
            ])
            
            if success:
                self.logger.info("   ✔️ Registry restored successfully")
                messagebox.showinfo(
                    "Success",
                    "Registry restored successfully.\n\nYou may need to restart for changes to take effect."
                )
            else:
                messagebox.showerror(
                    "Error",
                    "Registry restoration failed. Check logs for details."
                )
        except Exception as e:
            self.logger.info(f"   ❌ Restore error: {e}")
            messagebox.showerror("Error", str(e))

    def clear_logs(self):
        """Clear the logs display"""
        try:
            self.logs_text.delete("1.0", "end")
            self.logger.info("📋 Logs cleared")
        except Exception:
            pass

    def open_log_file(self):
        """Open the log file in default editor"""
        try:
            os.startfile(self.logger.log_file)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log file: {e}")


def main():
    """Entry point"""
    try:
        app = Win11OptimizerPro()
        app.mainloop()
    except Exception as e:
        messagebox.showerror(
            "Fatal Error",
            f"Application error:\n{e}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()