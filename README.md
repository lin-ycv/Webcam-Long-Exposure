# Webcam Long Exposure

A Python-based desktop application that turns your standard webcam into a long exposure camera. Perfect for light painting, capturing motion trails, or creative photography right from your computer.

## Features

- **Dual Exposure Modes**: 
  - **Additive**: Simulates a real sensor/film by accumulating light over time. Objects that stay in one place long enough appear brighter, while fast-moving lights leave graceful trails.
  - **Max Peak**: Keeps only the brightest pixels ever seen at each position. Ideal for high-contrast light painting where you want trails to never overlap or dim.
- **Live Contribution Slider**: Adjust the "opacity" or "speed" of accumulation (1% to 100%) in Additive mode.
- **Hardware Webcam Discovery**: Calls Windows DirectShow directly to display actual webcam names (e.g., "Logitech Brio") and instantaneous resolution polling via `pygrabber`.
- **Dynamic Resolution Control**: Quickly switch between all native resolutions supported by your hardware (up to 4K).
- **Standalone Executable**: Bundled with PyInstaller into a single, one-click Windows `.exe`.

## Requirements

If you want to run the application from the source code, you will need **Python 3.11+** and the following dependencies:

```bash
pip install opencv-python numpy Pillow pygrabber
```

## Usage

### Running the Pre-compiled Executable (Windows Only)
You don't need to install Python. Just grab the executable from the `release` and double click it.

*(Note: Because it is a single-file bundled executable, it may take 3-5 seconds to extract its dependencies to a temporary folder before the window appears).*

### Running from Source
1. Clone the repository.
2. Install dependencies: `pip install opencv-python numpy Pillow pygrabber`.
3. Run the script:
   ```bash
   python main.py
   ```

### Building the Executable
To bundle the script yourself using PyInstaller:
```bash
pyinstaller --onefile --windowed --hidden-import pygrabber --hidden-import pygrabber.dshow_graph main.py
```
Pwershell
```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts\pyinstaller.exe" --onefile --windowed --hidden-import pygrabber --hidden-import pygrabber.dshow_graph main.py
```

## Controls

- **Webcam Selector**: Choose which camera to use by its actual hardware name.
- **Resolution Dropdown**: Change capture quality on the fly.
- **Mode Toggle**: Switch between **Additive** and **Max Peak** logic.
- **Contribution Slider**: In Additive mode, this controls how quickly light builds up (e.g., set to 1% for very slow, cinematic light trails).
- **Start/Stop Exposure**: Control when the accumulation is active.
- **Reset**: Clears the current exposure buffer and returns to live view.
- **Save Image**: Export your capture as a high-quality `.jpg`.

## How it works under the hood

The application performs real-time image processing on the webcam stream:
1. **Additive Mode**: Each new frame is multiplied by the contribution percentage and added to a 32-bit floating-point accumulator. This integrates "photons" over time, meaning brighter/static objects saturate to white faster than moving ones.
2. **Max Peak Mode**: Uses `numpy.maximum()` to compare the current frame and the accumulator, keeping only the highest brightness value for every pixel.
3. **Hardware Query**: Uses `pygrabber` (DirectShow) to talk to Windows drivers, allowing for instant discovery of camera specifications without the slow trial-and-error polling typical of standard OpenCV.
