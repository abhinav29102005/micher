
import customtkinter as ctk
import math
import random
from micher.core.monitor import SystemNetworkMonitor, SystemSpeedSnapshot
from micher.gui.theme import *

def format_speed(bps):
    mbps = bps * 8 / 1_000_000
    if mbps >= 1000:
        return f"{mbps/1000:.1f} Gbps"
    return f"{mbps:.1f} Mbps"

class Particle:
    def __init__(self, x, y, target_x, target_y, speed, color):
        self.x = x
        self.y = y
        self.target_x = target_x
        self.target_y = target_y
        self.speed = speed
        self.color = color
        self.radius = random.randint(2, 4)
        
        dx = target_x - x
        dy = target_y - y
        dist = math.hypot(dx, dy)
        self.vx = (dx / dist) * speed if dist > 0 else 0
        self.vy = (dy / dist) * speed if dist > 0 else 0
        self.active = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        dist = math.hypot(self.target_x - self.x, self.target_y - self.y)
        if dist < self.speed:
            self.active = False

class MonitorDashboard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, **kwargs)
        
        self.monitor = SystemNetworkMonitor(interval=0.5)
        
        # Header
        self.header_label = ctk.CTkLabel(self, text="Real-Time Network Monitor", font=("Inter", 24, "bold"), text_color=TEXT_PRIMARY)
        self.header_label.pack(pady=(20, 0))
        
        # Canvas for animation
        self.canvas = ctk.CTkCanvas(self, bg=BG_DARK, highlightthickness=0, width=800, height=400)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.particles = []
        self.iface_positions = {}
        self.center_pos = (600, 200)
        
        # Global speed labels
        self.stats_frame = ctk.CTkFrame(self, fg_color=BG_CARD)
        self.stats_frame.pack(fill="x", padx=20, pady=20)
        
        self.down_label = ctk.CTkLabel(self.stats_frame, text="↓ 0.0 Mbps", font=("Inter", 32, "bold"), text_color=ACCENT_CYAN)
        self.down_label.pack(side="left", expand=True, pady=15)
        
        self.up_label = ctk.CTkLabel(self.stats_frame, text="↑ 0.0 Mbps", font=("Inter", 32, "bold"), text_color=ACCENT_GREEN)
        self.up_label.pack(side="right", expand=True, pady=15)
        
        self.monitor.start()
        self.update_animation()

    def update_animation(self):
        snapshot = self.monitor.get_snapshot()
        
        self.canvas.delete("all")
        width = self.canvas.winfo_width() or 800
        height = self.canvas.winfo_height() or 400
        self.center_pos = (width - 150, height // 2)
        
        # Draw central core
        r = 60
        cx, cy = self.center_pos
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=ACCENT_CYAN, width=3)
        self.canvas.create_text(cx, cy, text="Total Bandwidth", fill=TEXT_PRIMARY, font=("Inter", 12, "bold"))
        
        # Draw interface nodes
        active_ifaces = [iface for iface in snapshot.interfaces if iface.is_active or iface.name in self.iface_positions]
        if not active_ifaces:
            active_ifaces = snapshot.interfaces[:3] # Show at least a few
            
        n = len(active_ifaces)
        for i, iface in enumerate(active_ifaces):
            y = (height // (n + 1)) * (i + 1)
            x = 100
            self.iface_positions[iface.name] = (x, y)
            
            # Node
            self.canvas.create_oval(x-15, y-15, x+15, y+15, fill=BG_CARD, outline=TEXT_SECONDARY, width=2)
            self.canvas.create_text(x, y+25, text=iface.name, fill=TEXT_DIM, font=("Inter", 10))
            
            # Generate particles based on speed
            total_bps = iface.download_bps + iface.upload_bps
            mbps = total_bps * 8 / 1_000_000
            
            # Speed text
            self.canvas.create_text(x, y-25, text=format_speed(total_bps), fill=ACCENT_CYAN, font=("Inter", 10, "bold"))
            
            if total_bps > 0:
                spawn_count = min(int(mbps / 2) + 1, 15)
                for _ in range(spawn_count):
                    if random.random() < 0.4:
                        speed = random.uniform(5, 20)
                        self.particles.append(Particle(x, y, cx, cy, speed, ACCENT_CYAN))

        # Update particles
        new_particles = []
        for p in self.particles:
            p.update()
            if p.active:
                self.canvas.create_oval(p.x-p.radius, p.y-p.radius, p.x+p.radius, p.y+p.radius, fill=p.color, outline="")
                new_particles.append(p)
        self.particles = new_particles
        
        # Update labels
        self.down_label.configure(text=f"↓ {format_speed(snapshot.total_download_bps)}")
        self.up_label.configure(text=f"↑ {format_speed(snapshot.total_upload_bps)}")
        
        self.after(33, self.update_animation) # ~30 FPS

    def destroy(self):
        self.monitor.stop()
        super().destroy()
