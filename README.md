# LR 360 Viewer

<p align="center">
  <img src="assets/LR360Viewer.png" width="180" alt="LR 360 Viewer icon">
</p>

<p align="center">
  <strong>Interactive 360° reframe viewer for Adobe Lightroom Classic on Windows</strong>
</p>

<p align="center">
  <a href="https://github.com/lroubinov/LR360Viewer/releases/download/v1.0.0/LR360Viewer-v1.0.0-Windows.zip"><strong>⬇ Download LR 360 Viewer v1.0.0 for Windows</strong></a>
  &nbsp;•&nbsp;
  <a href="https://github.com/lroubinov/LR360Viewer/releases/latest">Latest Release</a>
</p>

> **Normal users:** download the Windows ZIP above. Do **not** download GitHub's automatically generated “Source code” ZIP/TAR files.

## What it does

LR 360 Viewer adds an interactive 360° reframe workflow to Adobe Lightroom Classic. Lightroom renders the selected stitched equirectangular panorama with your current Develop adjustments, then LR 360 Viewer lets you choose the view, projection, framing and output without leaving the Lightroom workflow.

## Features

- Native-looking Windows viewer using Microsoft Edge WebView2
- Linear, UltraWide, Tiny Planet, Mega View and Dewarp projections
- Studio-style Reframe panel
- Exact View Angle / FOV, Scale, Yaw, Pitch and Roll
- Aspect ratios: Original, 16:9, 9:16, 1:1, 4:5, 3:2 and 4:3
- Double-click **Look Here**
- Roll / Level controls
- Grid / thirds / center guides
- Shift + Drag fine movement
- Snapshots / multiple views and **Save All**
- High-resolution WebGL rendering
- JPEG and TIFF output
- Smart filenames
- Automatic import into Lightroom and stacking with the source photo
- Auto-hide UI and collapsible Reframe panel
- Standalone Windows EXE — Python is not required

## Installation

1. **Download:** [LR360Viewer-v1.0.0-Windows.zip](https://github.com/lroubinov/LR360Viewer/releases/download/v1.0.0/LR360Viewer-v1.0.0-Windows.zip)
2. Extract the ZIP to a permanent location, for example `C:\LR360Viewer\`.
3. After extraction you should have a folder named `LR360Viewer.lrplugin`.
4. Open Lightroom Classic.
5. Go to **File → Plug-in Manager**.
6. Click **Add** and select the extracted `LR360Viewer.lrplugin` folder.
7. Select a stitched 360° panorama in Lightroom.
8. Go to **Library → Plug-in Extras → View 360°**.

The release package contains the pre-built `LR360Viewer.exe`; users do not need Python or PyInstaller.

### Expected package structure

```text
LR360Viewer.lrplugin/
├── Info.lua
├── View360.lua
└── viewer/
    ├── LR360Viewer.exe
    ├── LR360Viewer.cmd
    ├── viewer.html
    └── ...
```

## Requirements

- Windows 10 or Windows 11
- Adobe Lightroom Classic
- Microsoft Edge WebView2 Runtime
- A stitched 2:1 equirectangular JPEG

## Saving a reframed image

**Save Perspective** renders the current projection, camera orientation, FOV, roll, aspect ratio and Lightroom Develop appearance at the selected output resolution. The saved image is written next to the original source and automatically imported back into Lightroom, stacked with the source photo.

## Insta360 `.INSP` files

LR 360 Viewer does not directly decode proprietary `.INSP` files. Stitch the image first in Insta360 Studio or another compatible stitcher and use the resulting equirectangular JPEG in Lightroom.

## Windows SmartScreen

The current public build is not digitally code-signed. Windows may therefore show an **Unknown publisher** / SmartScreen warning even though the EXE was built automatically from this public repository by GitHub Actions.

## For developers — building the EXE

```powershell
pip install -r requirements-build.txt
pyinstaller --clean --noconfirm LR360Viewer.spec
```

The executable is created at:

```text
dist/LR360Viewer.exe
```

GitHub Actions builds the Windows executable automatically and packages the complete Lightroom plug-in into the Release ZIP.

## License

MIT.

## Version

**v1.0.0** — first stable public release.
