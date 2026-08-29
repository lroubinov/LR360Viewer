# LR 360 Viewer

**LR 360 Viewer** is a Windows plug-in for Adobe Lightroom Classic that adds an interactive 360° reframe workflow for stitched equirectangular panoramas.

![LR 360 Viewer icon](assets/LR360Viewer.png)

## Highlights

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
- Custom Windows application icon

## Requirements

- Windows 10 or Windows 11
- Adobe Lightroom Classic
- Microsoft Edge WebView2 Runtime
- A stitched 2:1 equirectangular JPEG

The packaged release contains **LR360Viewer.exe**. Python is not required by normal users.

## Installation

1. Download `LR360Viewer-v1.0.0-Windows.zip` from **Releases**.
2. Extract `LR360Viewer.lrplugin` to a permanent location.
3. Lightroom Classic → **File → Plug-in Manager → Add**.
4. Select the `LR360Viewer.lrplugin` folder.
5. Select a stitched 360 panorama.
6. **Library → Plug-in Extras → View 360°**.

## How it works

Lightroom renders the selected panorama with the current Develop adjustments. LR 360 Viewer opens that rendered image in its 360 reframe engine.

**Save Perspective** writes the reframed image next to the original source file and automatically imports it into Lightroom, stacked below the source.

## Building the EXE

```powershell
pip install -r requirements-build.txt
pyinstaller --clean --noconfirm LR360Viewer.spec
```

The executable is created as:

```text
dist/LR360Viewer.exe
```

The GitHub Actions workflow builds the Windows EXE automatically and packages the complete Lightroom plug-in.

## Insta360 files

LR 360 Viewer does not decode proprietary `.INSP` files. Stitch the image first in Insta360 Studio or another compatible stitcher, then use the resulting equirectangular JPEG in Lightroom.

## License

MIT.

## Version

**v1.0.0** — first stable public release.
