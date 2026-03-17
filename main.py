import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from datetime import datetime
import os
import sys
import threading

try:
    from pygrabber.dshow_graph import FilterGraph as DShowFilterGraph
    _PYGRABBER_AVAILABLE = True
except Exception:
    _PYGRABBER_AVAILABLE = False
    DShowFilterGraph = None


def _get_cameras_via_dshow():
    """Returns {index: name} dict of all DirectShow cameras, near-instantly."""
    if not _PYGRABBER_AVAILABLE:
        return {}
    try:
        graph = DShowFilterGraph()
        names = graph.get_input_devices()
        return {i: name for i, name in enumerate(names)}
    except Exception:
        return {}


def _get_resolutions_via_dshow(index):
    """Returns sorted unique resolutions for a camera using DirectShow.
    Falls back to an empty list if unavailable (e.g. virtual cameras)."""
    if not _PYGRABBER_AVAILABLE:
        return []
    try:
        graph = DShowFilterGraph()
        graph.add_video_input_device(index)
        dev = graph.get_input_device()
        fmts = dev.get_formats()
        seen = set()
        results = []
        for f in fmts:
            vals = list(f.values())
            # Format dict values: [index, media_type, width, height, ...]
            w = int(vals[2]) if len(vals) > 2 else 0
            h = int(vals[3]) if len(vals) > 3 else 0
            key = (w, h)
            if key not in seen and w > 0 and h > 0:
                seen.add(key)
                results.append(f"{w}x{h}")
        return sorted(results, key=lambda x: int(x.split('x')[0]), reverse=True)
    except Exception:
        return []

class LongExposureApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.geometry("850x800")
        self.window.configure(bg="#2d2d2d")

        # State variables
        self.is_exposing = False
        self.accumulator = None
        self.current_display = None
        self.photo = None  # To hold the image reference
        self.vid = None
        self.camera_ready = False
        self.current_camera_index = 0
        self.available_cameras = []   # list of int indices
        self.camera_names = {}         # {index: display_name}
        self.camera_resolutions = {}   # {index: ["WxH", ...]}
        self.camera_var = tk.StringVar()
        self.camera_menu = None

        # Exposure mode: "additive" (duration matters) or "max" (peak-hold)
        self.exposure_mode = "additive"
        # Per-frame contribution percentage for additive mode (1-100)
        self.contribution_pct = tk.IntVar(value=50)

        # Status Label
        self.status_label = tk.Label(window, text="Starting UI... Please wait.", fg="white", bg="#2d2d2d", font=("Arial", 10))
        self.status_label.pack(side=tk.BOTTOM, pady=10)

        # UI Elements - Pack controls BEFORE canvas so they stay at the top
        # Resolutions handling
        self.supported_resolutions = []
        self.current_resolution = tk.StringVar()
        self.resolution_menu = None

        # Control Frame for buttons
        control_frame = tk.Frame(window, bg="#2d2d2d")
        control_frame.pack(side=tk.TOP, pady=10)
        
        # Camera Selection Frame (will populate after camera initializes)
        self.cam_frame = tk.Frame(window, bg="#2d2d2d")
        self.cam_frame.pack(side=tk.TOP, pady=5)
        
        # Resolutions Frame (will populate after camera initializes)
        self.res_frame = tk.Frame(window, bg="#2d2d2d")
        self.res_frame.pack(side=tk.TOP, pady=5)

        # Canvas for video
        self.canvas = tk.Canvas(window, width=640, height=480, bg="black", highlightthickness=0)
        self.canvas.pack(pady=20)

        # Buttons
        button_style = {
            "font": ("Arial", 12, "bold"),
            "bg": "#4CAF50",
            "fg": "white",
            "activebackground": "#45a049",
            "activeforeground": "white",
            "padx": 15,
            "pady": 8,
            "bd": 0,
            "cursor": "hand2"
        }
        
        stop_style = button_style.copy()
        stop_style.update({"bg": "#f44336", "activebackground": "#da190b"})
        
        neutral_style = button_style.copy()
        neutral_style.update({"bg": "#2196F3", "activebackground": "#0b7dda"})

        self.btn_start = tk.Button(control_frame, text="Start Exposure", command=self.start_exposure, **button_style)
        self.btn_start.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(control_frame, text="Stop Exposure", command=self.stop_exposure, state=tk.DISABLED, **stop_style)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        self.btn_reset = tk.Button(control_frame, text="Reset", command=self.reset_exposure, **neutral_style)
        self.btn_reset.pack(side=tk.LEFT, padx=10)

        self.btn_save = tk.Button(control_frame, text="Save Image", command=self.save_image, **neutral_style)
        self.btn_save.pack(side=tk.LEFT, padx=10)

        # Mode toggle + contribution slider row
        mode_frame = tk.Frame(window, bg="#2d2d2d")
        mode_frame.pack(side=tk.TOP, pady=(0, 5))

        toggle_style = neutral_style.copy()
        toggle_style.update({"bg": "#9C27B0", "activebackground": "#7B1FA2",
                             "font": ("Arial", 10, "bold"), "padx": 10, "pady": 5})
        self.btn_mode = tk.Button(mode_frame, text="Mode: Additive", command=self._toggle_mode, **toggle_style)
        self.btn_mode.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(mode_frame, text="Contribution:", bg="#2d2d2d", fg="#aaaaaa", font=("Arial", 10)).pack(side=tk.LEFT)
        self.slider_contribution = tk.Scale(
            mode_frame, from_=1, to=100, orient=tk.HORIZONTAL,
            variable=self.contribution_pct, length=180,
            bg="#2d2d2d", fg="white", highlightthickness=0,
            troughcolor="#555555", activebackground="#9C27B0",
            font=("Arial", 9), label=""
        )
        self.slider_contribution.pack(side=tk.LEFT, padx=5)
        tk.Label(mode_frame, text="%", bg="#2d2d2d", fg="#aaaaaa", font=("Arial", 10)).pack(side=tk.LEFT)
        
        # Update cycle
        self.delay = 15 # ms
        
        # Start the one persistent video loop immediately.
        # It will idle (skip rendering) until camera_ready is True.
        self.window.after(self.delay, self.update)

        # Schedule camera init
        self.window.after(100, self.init_camera)

        # Handle window closure
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_camera(self):
        self.status_label.config(text="Status: Discovering available cameras... this may take a few seconds.")
        self.window.update()
        
        # Start asynchronous polling for cameras and their resolutions
        self.polling_done = False
        threading.Thread(target=self.poll_cameras_and_resolutions, daemon=True).start()
        self.window.after(100, self._check_polling_status)

    def poll_cameras_and_resolutions(self, old_vid=None):
        # DirectShow (COM) must be initialized per thread on Windows
        try:
            import ctypes
            ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED=0
        except Exception:
            pass

        # 0. Close the old video capture safely in the background thread
        if old_vid is not None and old_vid.isOpened():
            old_vid.release()

        # 1. Find all available cameras using DirectShow (fast, gets real names)
        if not self.available_cameras:
            dshow_cameras = _get_cameras_via_dshow()
            if dshow_cameras:
                # Trust DirectShow for the authoritative device list + names
                self.camera_names = dshow_cameras
                self.available_cameras = sorted(dshow_cameras.keys())
            else:
                # Fallback: probe indices 0-4 with OpenCV
                for i in range(5):
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        self.available_cameras.append(i)
                        self.camera_names[i] = f"Camera {i}"
                        cap.release()

        if not self.available_cameras:
            self.polling_done = True
            return

        # Select the first available camera if the current index is invalid
        if self.current_camera_index not in self.available_cameras:
            self.current_camera_index = self.available_cameras[0]

        # 2. Open the selected camera
        self.vid = cv2.VideoCapture(self.current_camera_index, cv2.CAP_DSHOW)

        # 3. Get resolutions — try DirectShow first (instant), fall back to polling
        if self.current_camera_index not in self.camera_resolutions:
            fast_res = _get_resolutions_via_dshow(self.current_camera_index)
            if fast_res:
                self.supported_resolutions = fast_res
                # Apply the best resolution immediately
                if self.supported_resolutions:
                    best_w, best_h = map(int, self.supported_resolutions[0].split('x'))
                    self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, best_w)
                    self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, best_h)
            else:
                # Fallback: slow OpenCV trial-and-error (for virtual cameras etc.)
                self._poll_resolutions_internal()
            self.camera_resolutions[self.current_camera_index] = self.supported_resolutions
        else:
            self.supported_resolutions = self.camera_resolutions[self.current_camera_index]
            if self.supported_resolutions:
                best_w, best_h = map(int, self.supported_resolutions[0].split('x'))
                self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, best_w)
                self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, best_h)

        self.polling_done = True

    def _check_polling_status(self):
        if self.polling_done:
            if not self.vid or not self.vid.isOpened():
                 self.status_label.config(text="Status: Error - Could not open any webcam.")
                 messagebox.showerror("Camera Error", "Could not connect to a webcam. Please verify it is connected.")
                 return
                 
            self.setup_ui_dropdowns()
            
            # Calculate display size to fit within a sane window
            self.actual_w = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.actual_h = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if self.actual_w > 0 and self.actual_h > 0:
                scale = min(1.0, 800 / self.actual_w, 600 / self.actual_h)
                self.disp_w = int(self.actual_w * scale)
                self.disp_h = int(self.actual_h * scale)
                self.canvas.config(width=self.disp_w, height=self.disp_h)

            self.camera_ready = True
            self.status_label.config(text=f"Status: Ready. Recording Resolution: {self.actual_w}x{self.actual_h}")
            # The persistent update() loop is already running — no need to restart it.
        else:
            self.window.after(100, self._check_polling_status)

    def _poll_resolutions_internal(self):
        """ Tests standard resolutions and records which ones are accepted by the hardware """
        self.supported_resolutions = []
        standard_resolutions = [
            (3840, 2160), (2560, 1440), (1920, 1080), 
            (1280, 720), (1024, 768), (800, 600), (640, 480)
        ]
        
        for w, h in standard_resolutions:
            self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            
            # Read back what the camera actually applied
            actual_w = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            res_string = f"{actual_w}x{actual_h}"
            if res_string not in self.supported_resolutions and actual_w > 0:
                self.supported_resolutions.append(res_string)
                
        # Set length might be 0 if the camera failed entirely. Protect against it.
        if self.supported_resolutions:
            best_w, best_h = map(int, self.supported_resolutions[0].split('x'))
            self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, best_w)
            self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, best_h)

    def setup_ui_dropdowns(self):
        # 1. Setup Camera Dropdown (only once)
        if self.available_cameras and self.camera_menu is None:
            tk.Label(self.cam_frame, text="Camera:", bg="#2d2d2d", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

            # Use real hardware names, e.g. "Logi C310 HD WebCam"
            cam_options = [self.camera_names.get(i, f"Camera {i}") for i in self.available_cameras]
            self.camera_var.set(self.camera_names.get(self.current_camera_index, f"Camera {self.current_camera_index}"))

            self.camera_menu = tk.OptionMenu(self.cam_frame, self.camera_var, *cam_options, command=self.change_camera)
            self.camera_menu.config(bg="#2d2d2d", fg="white", highlightthickness=0)
            self.camera_menu.pack(side=tk.LEFT)

        # 2. Setup/Update Resolution Dropdown
        if not self.supported_resolutions:
            return

        for widget in self.res_frame.winfo_children():
            widget.destroy()
        self.resolution_menu = None

        tk.Label(self.res_frame, text="Resolution:", bg="#2d2d2d", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.current_resolution.set(self.supported_resolutions[0])
        self.resolution_menu = tk.OptionMenu(self.res_frame, self.current_resolution, *self.supported_resolutions, command=self.change_resolution)
        self.resolution_menu.config(bg="#2d2d2d", fg="white", highlightthickness=0)
        self.resolution_menu.pack(side=tk.LEFT)

    def change_camera(self, selection):
        # Resolve the selected name back to an index
        new_index = None
        for idx in self.available_cameras:
            if self.camera_names.get(idx, f"Camera {idx}") == selection:
                new_index = idx
                break
        if new_index is None or new_index == self.current_camera_index:
            return

        self.status_label.config(text=f"Status: Switching to {selection}...")
        self.window.update()

        self.camera_ready = False
        self.reset_exposure()
        self.current_camera_index = new_index

        # Pass old vid to background thread for safe release
        old_vid = self.vid
        self.vid = None
        self.supported_resolutions = []

        self.polling_done = False
        threading.Thread(target=self.poll_cameras_and_resolutions, args=(old_vid,), daemon=True).start()
        self.window.after(100, self._check_polling_status)

    def change_resolution(self, selection):
        if not self.camera_ready:
            return
            
        selected = self.current_resolution.get()
        if not selected or 'x' not in selected:
            return
            
        w, h = map(int, selected.split('x'))
        
        self.status_label.config(text=f"Status: Switching resolution to {w}x{h}...")
        self.window.update()
        
        # We need to temporarily halt operations and reset the accumulator
        self.camera_ready = False
        self.reset_exposure()
        
        # Set the new resolution
        self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        
        # Wait a beat to let it apply, then confirm and resize canvas
        self.window.after(500, self._apply_new_resolution_ui)
        
    def _apply_new_resolution_ui(self):
        self.actual_w = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_h = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if self.actual_w > 0 and self.actual_h > 0:
            scale = min(1.0, 800 / self.actual_w, 600 / self.actual_h)
            self.disp_w = int(self.actual_w * scale)
            self.disp_h = int(self.actual_h * scale)
            self.canvas.config(width=self.disp_w, height=self.disp_h)
            
        self.status_label.config(text=f"Status: Ready. Recording Resolution: {self.actual_w}x{self.actual_h}")
        self.camera_ready = True

    def start_exposure(self):
        if not self.camera_ready:
            return
        self.is_exposing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="Status: EXPOSING... Move lights around!")

    def stop_exposure(self):
        self.is_exposing = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Paused Exposure")

    def reset_exposure(self):
        self.is_exposing = False
        self.accumulator = None
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Reset. Ready.")

    def save_image(self):
        if self.current_display is not None:
            # Create a filename based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"long_exposure_{timestamp}.jpg"
            
            # Save using OpenCV
            cv2.imwrite(filename, self.current_display)
            messagebox.showinfo("Saved", f"Image saved successfully as:\n{filename}")
            self.status_label.config(text=f"Status: Saved {filename}")
        else:
            messagebox.showwarning("Warning", "No image to save yet!")

    def _toggle_mode(self):
        if self.exposure_mode == "additive":
            self.exposure_mode = "max"
            self.btn_mode.config(text="Mode: Max Peak")
            # Slider is irrelevant in max mode — grey it out
            self.slider_contribution.config(state=tk.DISABLED)
        else:
            self.exposure_mode = "additive"
            self.btn_mode.config(text="Mode: Additive")
            self.slider_contribution.config(state=tk.NORMAL)
        # Reset accumulator so switching modes starts fresh
        self.accumulator = None

    def update(self):
        try:
            if self.camera_ready and self.vid is not None and self.vid.isOpened():
                ret, frame = self.vid.read()

                if ret:
                    frame = cv2.flip(frame, 1)

                    if self.is_exposing:
                        if self.exposure_mode == "additive":
                            contrib = self.contribution_pct.get() / 100.0
                            weighted = frame.astype(np.float32) * contrib
                            if self.accumulator is None:
                                self.accumulator = weighted
                            else:
                                self.accumulator += weighted
                        else:  # max-peak mode
                            if self.accumulator is None:
                                self.accumulator = frame.astype(np.float32)
                            else:
                                np.maximum(self.accumulator, frame, out=self.accumulator)
                        self.current_display = np.clip(self.accumulator, 0, 255).astype(np.uint8)
                    else:
                        if self.accumulator is not None:
                            self.current_display = np.clip(self.accumulator, 0, 255).astype(np.uint8)
                        else:
                            self.current_display = frame.copy()

                    cv_image = cv2.cvtColor(self.current_display, cv2.COLOR_BGR2RGB)
                    if hasattr(self, 'disp_w') and (self.disp_w != self.actual_w or self.disp_h != self.actual_h):
                        cv_image = cv2.resize(cv_image, (self.disp_w, self.disp_h), interpolation=cv2.INTER_AREA)
                    pil_image = Image.fromarray(cv_image)
                    self.photo = ImageTk.PhotoImage(image=pil_image)
                    self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
        except Exception:
            pass  # Never let an exception kill the update loop
        finally:
            # Always reschedule — this loop must never die
            self.window.after(self.delay, self.update)

    def on_closing(self):
        if self.vid and self.vid.isOpened():
            self.vid.release()
        self.window.destroy()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

if __name__ == '__main__':
    # Create the main window and start the application
    root = tk.Tk()
    
    # Optional: set a simple icon if we had one
    # try:
    #     root.iconbitmap(resource_path("icon.ico"))
    # except:
    #     pass
        
    app = LongExposureApp(root, "Webcam Long Exposure App")
    root.mainloop()
