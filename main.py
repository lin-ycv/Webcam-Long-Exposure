import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from datetime import datetime
import os
import sys
import threading

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
        
        # Update cycle
        self.delay = 15 # ms
        
        # Schedule camera init
        self.window.after(100, self.init_camera)

        # Handle window closure
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_camera(self):
        self.status_label.config(text="Status: Initializing camera... this may take a few seconds.")
        self.window.update()
        
        # OpenCV VideoCapture (0 for default webcam) with DSHOW for much faster startup on Windows
        self.vid = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        
        if not self.vid.isOpened():
             print("Camera failed to open!")
             self.status_label.config(text="Status: Error - Could not open webcam.")
             messagebox.showerror("Camera Error", "Could not connect to a webcam. Please verify it is connected and not used by another application.")
             return

        # Start asynchronous polling
        if not self.supported_resolutions:
             self.status_label.config(text="Status: Polling camera resolutions... please wait.")
             self.polling_done = False
             threading.Thread(target=self.poll_resolutions, daemon=True).start()
             self.window.after(100, self._check_polling_status)
        else:
             self.polling_done = True
             self._check_polling_status()

    def _check_polling_status(self):
        if self.polling_done:
            self.setup_resolution_dropdown()
            
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
            
            # Start the video loop
            self.update()
        else:
            self.window.after(100, self._check_polling_status)

    def poll_resolutions(self):
        """ Tests standard resolutions and records which ones are accepted by the hardware """
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
                
        # Set the camera back to the highest supported resolution by default
        if self.supported_resolutions:
            best_w, best_h = map(int, self.supported_resolutions[0].split('x'))
            self.vid.set(cv2.CAP_PROP_FRAME_WIDTH, best_w)
            self.vid.set(cv2.CAP_PROP_FRAME_HEIGHT, best_h)
            
        self.polling_done = True

    def setup_resolution_dropdown(self):
        if not self.supported_resolutions:
             return
             
        # Create a dropdown menu mapped to a Tkinter string variable
        tk.Label(self.res_frame, text="Resolution:", bg="#2d2d2d", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        self.current_resolution.set(self.supported_resolutions[0]) # Default value
        
        # Use trace to call change_resolution whenever the dropdown value changes
        self.current_resolution.trace_add("write", self.change_resolution)
        
        self.resolution_menu = tk.OptionMenu(self.res_frame, self.current_resolution, *self.supported_resolutions)
        self.resolution_menu.config(bg="#2d2d2d", fg="white", highlightthickness=0)
        self.resolution_menu.pack(side=tk.LEFT)

    def change_resolution(self, *args):
        if not self.camera_ready:
            return
            
        selected = self.current_resolution.get()
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

    def update(self):
        if not self.camera_ready:
            # Re-schedule the update loop so it doesn't permanently die while paused
            self.window.after(self.delay, self.update)
            return
             
        ret, frame = self.vid.read()

        if ret:
            # Flip frame horizontally for a mirror effect (more natural to use)
            frame = cv2.flip(frame, 1)
            
            if self.is_exposing:
                if self.accumulator is None:
                    self.accumulator = frame.copy()
                else:
                    # Compare and take the max pixel values
                    self.accumulator = np.maximum(self.accumulator, frame)
                
                # We show the accumulated frame
                self.current_display = self.accumulator.copy()
            else:
                if self.accumulator is not None:
                     # When paused but have data, show the accumulator
                     self.current_display = self.accumulator.copy()
                else:
                     # When not exposing and no data, show live feed
                     self.current_display = frame.copy()

            # Convert to PIL Image and then Tkinter ImageTk format
            # OpenCV is BGR, PIL needs RGB
            cv_image = cv2.cvtColor(self.current_display, cv2.COLOR_BGR2RGB)
            
            # Scale down for display if needed
            if hasattr(self, 'disp_w') and (self.disp_w != self.actual_w or self.disp_h != self.actual_h):
                cv_image = cv2.resize(cv_image, (self.disp_w, self.disp_h), interpolation=cv2.INTER_AREA)

            pil_image = Image.fromarray(cv_image)
            self.photo = ImageTk.PhotoImage(image=pil_image)

            # Update Canvas
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        # Loop
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
