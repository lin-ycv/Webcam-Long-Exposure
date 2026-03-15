# Webcam Long Exposure

A Python-based desktop application that turns your standard webcam into a long exposure camera. By continuously analyzing the live video feed and accumulating the brightest pixels over time, it simulates the effect of a long exposure photograph—perfect for light painting, capturing motion trails, or creative photography right from your computer.

## Features

- **Real-time Long Exposure**: Computes long exposure mathematically by keeping the maximum pixel values (`np.maximum`) across frames.
- **Dynamic Resolution Polling**: Automatically queries your webcam hardware on startup to discover and list all supported native resolutions (from 480p up to 4K).
- **Responsive UI**: Built with Tkinter, featuring a background polling thread so the app opens instantly without freezing while loading.
- **Smart Display Scaling**: Downscales high-resolution feeds (like 4K) to fit nicely on your monitor during live preview, while still saving the final image at the full, native resolution.
- **Export Functionality**: Easily export your long-exposure captures as timestamped `.jpg` images.
- **Standalone Executable**: Bundled with PyInstaller into a single, one-click Windows `.exe` file that doesn't require Python to be installed.

## Requirements

If you want to run the application from the source code, you will need **Python 3.x** and the following dependencies:

```bash
pip install opencv-python numpy Pillow
```

## Usage

### Running the Pre-compiled Executable (Windows Only)
You don't need to install Python. Just grab the executable from the `release` folder and double click it.

*(Note: Because it is a single-file bundled executable, it may take 3-5 seconds to extract its dependencies to a temporary folder before the window appears).*

### Running from Source
If you are modifying the code or running on macOS/Linux:
1. Clone the repository.
2. Install the requirements (`pip install opencv-python numpy Pillow`).
3. Run the script:
   ```bash
   python main.py
   ```

## Controls

Once the application launches and the camera initializes:

- **Resolution Dropdown**: Select the desired capture resolution. The camera stream will briefly pause while the hardware switches over.
- **Start Exposure**: Begins capturing the brightest pixels. Move a light source (like your phone flashlight or glowsticks) in front of the camera to start painting!
- **Stop Exposure**: Pauses the accumulation so you can preview your final result without adding new light.
- **Reset**: Clears the current exposure buffer and returns to the standard live webcam feed.
- **Save Image**: Exports the current exposure to the application directory as a high-resolution `.jpg` file.

## How it works under the hood
Because standard webcams don't have adjustable physical analog shutters, this software replicates a long exposure computationally.
1. It reads frames continuously using OpenCV (`cv2.VideoCapture`).
2. When "Exposing" is active, it compares the current frame against a running "accumulator" numpy array.
3. Using `numpy.maximum()`, it updates the accumulator with the brightest value for every single pixel. This means a moving light source leaves a permanent trail on the image while stationary dark backgrounds remain dark.
