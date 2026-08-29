# Lightroom 360 Viewer

<p align="center">
  <img src="assets/LR360Viewer.png" width="180" alt="Lightroom 360 Viewer icon">
</p>

<p align="center">
  <strong>Interactive 360° reframe viewer for Adobe Lightroom Classic on Windows</strong>
</p>

<p align="center">
  <a href="https://github.com/lroubinov/LR360Viewer/releases/download/v1.1.0/LR360Viewer-v1.1.0-Windows.zip"><strong>⬇ Download Lightroom 360 Viewer v1.1.0 for Windows</strong></a>
  &nbsp;•&nbsp;
  <a href="https://github.com/lroubinov/LR360Viewer/releases/latest">Latest Release</a>
</p>

> **Normal users:** download the Windows ZIP above. Do **not** download GitHub's automatically generated “Source code” ZIP/TAR files.

## What it does

Lightroom 360 Viewer adds an interactive 360° reframe workflow to Adobe Lightroom Classic. Keep the viewer open while you move through the Filmstrip or Grid: Live Link follows Lightroom's active photo and loads its source file directly for fast browsing. A Lightroom render with the current Develop adjustments is created only when you click **Apply Lightroom Edits**.

The viewer can be launched from **Plug-in Extras** or configured as a Lightroom **External Editor**. When the plug-in is installed and Lightroom is running, External Editor mode automatically connects to the same Live Link workflow.

## Features

- Live Link to the active Lightroom photo in Filmstrip and Grid
- Fast source-file switching without a Lightroom render on every photo
- On-demand **Apply Lightroom Edits** render with current Develop adjustments
- Works both as a Lightroom plug-in and as an External Editor
- Automatic fallback for source formats that WebView2 cannot display directly
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

1. **Download:** [LR360Viewer-v1.1.0-Windows.zip](https://github.com/lroubinov/LR360Viewer/releases/download/v1.1.0/LR360Viewer-v1.1.0-Windows.zip)
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
├── Init.lua
├── View360.lua
└── viewer/
    ├── LR360Viewer.exe
    ├── LR360Viewer.cmd
    ├── viewer.html
    └── ...
```

### Plug-in mode

Select the active panorama and choose **Library → Plug-in Extras → View 360°**. The viewer opens immediately from the source file. Changing the active photo in Lightroom updates the open viewer automatically after a short debounce.

Click **Apply Lightroom Edits** whenever you want Lightroom to render the active photo with its current Develop settings. The viewer then replaces the direct source preview with that rendered version.

### External Editor mode with Live Link

1. Keep the `LR360Viewer.lrplugin` plug-in installed and enabled.
2. In Lightroom Classic, open **Edit → Preferences → External Editing**.
3. Under **Additional External Editor**, choose `LR360Viewer.exe` from `LR360Viewer.lrplugin\viewer\`.
4. Configure the external edit format as JPEG or TIFF.
5. Send a photo to the configured editor from Lightroom.

The viewer first opens in External Editor mode and then connects automatically. The status changes to **External Editor - Live Link**. You can now move through Filmstrip/Grid and use **Apply Lightroom Edits** exactly as in plug-in mode.

If Lightroom or the plug-in bridge is unavailable, the viewer remains usable as a normal External Editor and saves back to the JPEG/TIFF copy supplied by Lightroom.

## Requirements

- Windows 10 or Windows 11
- Adobe Lightroom Classic
- Microsoft Edge WebView2 Runtime
- A stitched 2:1 equirectangular image; unsupported direct-preview formats can use **Apply Lightroom Edits**

## Saving a reframed image

**Save Perspective** renders the current projection, camera orientation, FOV, roll, scale and aspect ratio at the selected output resolution. In Plug-in mode and External Editor Live Link mode, the saved image is written next to the original source, imported into Lightroom and stacked with that source photo.

The direct source preview does not include Lightroom Develop adjustments. Click **Apply Lightroom Edits** before saving when the result should use Lightroom's current Develop appearance.

## Insta360 `.INSP` files

Lightroom 360 Viewer does not directly decode proprietary `.INSP` files. Stitch the image first in Insta360 Studio or another compatible stitcher and use the resulting equirectangular JPEG in Lightroom.

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

**v1.1.0** — adds active-photo Live Link, on-demand Lightroom Develop rendering and hybrid External Editor support.
