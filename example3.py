import tkinter as tk
from tkinter import ttk
import math
import time

class HyperXVisualizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hyper X Manager - GPU Virtualization Visualizer")
        self.root.geometry("1100x750")
        self.root.configure(bg="#1c1d22")

        # use sleek dark theme
        self.setup_styles()
        
        # main container layout
        self.main_frame = tk.Frame(self.root, bg="#1c1d22", padx=20, pady=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_frame, bg="#1c1d22")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.right_frame = tk.Frame(self.main_frame, bg="#1c1d22")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self.build_status_panel()
        self.build_vram_panel()
        self.build_registers_panel()
        
        self.build_canvas_panel()
        self.build_logs_panel()

        # rotation state for the triangle animation
        self.angle = 0
        self.animate_triangle()

        # event logs queue index
        self.log_index = 0
        self.logs_feed = [
            ("VMM", "Initialized WHPX backend successfully", "info"),
            ("WHPX", "Mapped GPA 0x00000000 - 0x08000000 (128MB RAM)", "info"),
            ("WHPX", "Mapped GPA 0x40000000 - 0x50000000 (256MB Shared VRAM)", "info"),
            ("VMM", "Direct Boot: loaded bzImage into guest RAM (entry 0x100000)", "info"),
            ("EXIT", "Port write to 0x3F8: [   0.000000] Linux version 6.1.0-21-amd64", "exit"),
            ("EXIT", "Port write to 0x3F8: [   0.000000] Command line: console=ttyS0 quiet", "exit"),
            ("EXIT", "Port write to 0x3F8: [   0.245100] Initializing local APIC timer...", "exit"),
            ("EXIT", "Port write to 0x3F8: [   1.104230] Platform Device hyperx_drm registered successfully", "exit"),
            ("EXIT", "Port write to 0x3F8: [   1.458900] hyperx_drm: mapped VRAM GPA at 0x40000000", "exit"),
            ("XGPU", "Doorbell write exit on 0x3FFFF000 (XGPU_CMD_INIT)", "gpu"),
            ("XGPU", "Host Vulkan Instance initialized on physical GPU: NVIDIA GeForce RTX", "gpu"),
            ("XGPU", "Doorbell write exit on 0x3FFFF000 (XGPU_CMD_ALLOC_MEM)", "gpu"),
            ("XGPU", "Allocated 100MB native VRAM mirror at offset 0x1000", "gpu"),
            ("XGPU", "Doorbell write exit on 0x3FFFF000 (XGPU_CMD_VK_SUBMIT)", "gpu"),
            ("XGPU", "Directly submitting raw command buffers to host GPU queue", "gpu")
        ]
        self.update_logs()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1c1d22", foreground="#f8f9fa")
        style.configure("Card.TFrame", background="#25262c", borderwidth=1, relief="solid")

    def build_status_panel(self):
        # header status card (modern rounded style)
        card = tk.Frame(self.left_frame, bg="#25262c", bd=1, relief="solid", highlightbackground="#313238", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 15))
        
        lbl = tk.Label(card, text="VM: hyperx-guest-vm", font=("Outfit", 14, "bold"), fg="#ffffff", bg="#25262c", padx=15, pady=10)
        lbl.pack(side=tk.LEFT)
        
        status_container = tk.Frame(card, bg="#25262c")
        status_container.pack(side=tk.RIGHT, padx=15)
        
        dot = tk.Label(status_container, text="●", fg="#00f5d4", bg="#25262c", font=("Outfit", 12))
        dot.pack(side=tk.LEFT)
        
        status_lbl = tk.Label(status_container, text="Active (WHPX)", font=("Outfit", 10, "bold"), fg="#00f5d4", bg="#25262c", padx=5)
        status_lbl.pack(side=tk.LEFT)

    def build_vram_panel(self):
        # shared memory visualizer grid
        card = tk.Frame(self.left_frame, bg="#25262c", bd=1, relief="solid", highlightbackground="#313238", highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, pady=10)
        
        title = tk.Label(card, text="SHARED VRAM LAYOUT (256MB)", font=("Outfit", 10, "bold"), fg="#adb5bd", bg="#25262c", padx=15, pady=10)
        title.pack(anchor="w")

        grid_frame = tk.Frame(card, bg="#25262c", padx=15, pady=5)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        # draw 8x8 block grid to represent memory sectors
        self.blocks = []
        for r in range(8):
            row_blocks = []
            for c in range(8):
                color = "#2c2d35" # default empty
                idx = r * 8 + c
                if idx < 4:
                    color = "#00bbf9" # ring buffer
                elif idx >= 8 and idx < 24:
                    color = "#9d4edd" # vertex data
                elif idx >= 32 and idx < 48:
                    color = "#00f5d4" # active framebuffers
                
                block = tk.Frame(grid_frame, width=32, height=32, bg=color, bd=1, relief="raised")
                block.grid(row=r, column=c, padx=3, pady=3)
                row_blocks.append(block)
            self.blocks.append(row_blocks)

        # legend panel
        legend = tk.Frame(card, bg="#25262c", pady=10)
        legend.pack(fill=tk.X)
        
        colors = [("#00bbf9", "Ring Buffer"), ("#9d4edd", "Vertex Data"), ("#00f5d4", "Framebuffers")]
        for color, name in colors:
            item = tk.Frame(legend, bg="#25262c", padx=15)
            item.pack(side=tk.LEFT)
            box = tk.Frame(item, width=12, height=12, bg=color)
            box.pack(side=tk.LEFT, padx=(0, 5))
            lbl = tk.Label(item, text=name, font=("Outfit", 8), fg="#adb5bd", bg="#25262c")
            lbl.pack(side=tk.LEFT)

    def build_registers_panel(self):
        # virtual cpu registers
        card = tk.Frame(self.left_frame, bg="#25262c", bd=1, relief="solid", highlightbackground="#313238", highlightthickness=1)
        card.pack(fill=tk.X, pady=(15, 0))
        
        title = tk.Label(card, text="VIRTUAL PROCESSOR REGISTERS", font=("Outfit", 10, "bold"), fg="#adb5bd", bg="#25262c", padx=15, pady=10)
        title.pack(anchor="w")

        reg_frame = tk.Frame(card, bg="#25262c", padx=15, pady=10)
        reg_frame.pack(fill=tk.X)

        self.regs = {
            "RIP": "0x00100000", "RSI": "0x00010000",
            "RSP": "0x00008000", "CR0": "0x00000001",
            "CS": "0x0008", "DS": "0x0010"
        }
        self.reg_labels = {}
        
        r = 0
        c = 0
        for name, val in self.regs.items():
            box = tk.Frame(reg_frame, bg="#1c1d22", bd=1, relief="solid", padx=10, pady=6)
            box.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            reg_frame.grid_columnconfigure(c, weight=1)
            
            lbl_name = tk.Label(box, text=name, font=("JetBrains Mono", 9, "bold"), fg="#c77dff", bg="#1c1d22")
            lbl_name.pack(side=tk.LEFT)
            
            lbl_val = tk.Label(box, text=val, font=("JetBrains Mono", 9), fg="#ffffff", bg="#1c1d22")
            lbl_val.pack(side=tk.RIGHT)
            self.reg_labels[name] = lbl_val
            
            c += 1
            if c > 1:
                c = 0
                r += 1

    def build_canvas_panel(self):
        # host renderer frame
        card = tk.Frame(self.right_frame, bg="#25262c", bd=1, relief="solid", highlightbackground="#313238", highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        title = tk.Label(card, text="HOST RENDERING PIPELINE (X-GPU)", font=("Outfit", 10, "bold"), fg="#adb5bd", bg="#25262c", padx=15, pady=10)
        title.pack(anchor="w")

        self.canvas = tk.Canvas(card, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        self.fps_lbl = tk.Label(self.canvas, text="Host Vulkan Renderer | 60 FPS", font=("JetBrains Mono", 8), fg="#00f5d4", bg="#000000")
        self.fps_lbl.place(x=10, y=10)

    def build_logs_panel(self):
        # terminal logs
        card = tk.Frame(self.right_frame, bg="#25262c", bd=1, relief="solid", highlightbackground="#313238", highlightthickness=1)
        card.pack(fill=tk.X, pady=(10, 0))
        
        title = tk.Label(card, text="HYPERVISOR DOORBELL EXITS", font=("Outfit", 10, "bold"), fg="#adb5bd", bg="#25262c", padx=15, pady=10)
        title.pack(anchor="w")

        self.logs_box = tk.Text(card, bg="#000000", fg="#f8f9fa", font=("JetBrains Mono", 9), height=11, bd=0, padx=10, pady=10)
        self.logs_box.pack(fill=tk.X, padx=15, pady=(0, 15))
        self.logs_box.configure(state=tk.DISABLED)

    def animate_triangle(self):
        self.canvas.delete("triangle")
        
        cx, cy = 200, 150 # canvas center
        r = 80 # radius
        
        # calculate coordinates of rotating triangle
        pts = []
        for i in range(3):
            theta = self.angle + (i * 2 * math.pi / 3)
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            pts.append((x, y))
            
        self.canvas.create_polygon(
            pts[0][0], pts[0][1], pts[1][0], pts[1][1], pts[2][0], pts[2][1],
            fill="#9d4edd", outline="#00f5d4", width=2, tag="triangle"
        )
        
        self.angle += 0.04
        self.root.after(30, self.animate_triangle)

    def update_logs(self):
        if self.log_index < len(self.logs_feed):
            tag, msg, style_type = self.logs_feed[self.log_index]
            self.logs_box.configure(state=tk.NORMAL)
            
            timestamp = time.strftime("[%H:%M:%S]")
            log_line = f"{timestamp} [{tag}] {msg}\n"
            
            self.logs_box.insert(tk.END, log_line)
            self.logs_box.see(tk.END)
            self.logs_box.configure(state=tk.DISABLED)
            
            # dynamically update registers
            rip_hex = f"0x00{0x100000 + self.log_index * 0x4B3:08X}"
            self.reg_labels["RIP"].configure(text=rip_hex)
            
            self.log_index += 1
        else:
            self.log_index = 0
            self.logs_box.configure(state=tk.NORMAL)
            self.logs_box.delete("1.0", tk.END)
            self.logs_box.configure(state=tk.DISABLED)

        self.root.after(2000, self.update_logs)

if __name__ == "__main__":
    root = tk.Tk()
    app = HyperXVisualizerApp(root)
    root.mainloop()
