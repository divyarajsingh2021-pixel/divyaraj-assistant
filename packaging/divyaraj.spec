"""One-folder, windowed PyInstaller build for Divyaraj Assistant."""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

ROOT = Path(SPECPATH).resolve().parent
datas = []
binaries = []
hiddenimports = []

for package in (
    "customtkinter",
    "faster_whisper",
    "onnxruntime",
    "PIL",
    "pystray",
    "pynput",
    "sounddevice",
    "ctranslate2",
    "huggingface_hub",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    if package == "onnxruntime":
        package_datas = [
            (source, destination)
            for source, destination in package_datas
            if "/datasets/" not in source.replace("\\", "/").lower()
        ]
    datas += package_datas
    binaries += package_binaries
    if package != "onnxruntime":
        hiddenimports += package_hiddenimports

datas += collect_data_files(
    "piper",
    excludes=["**/*.onnx", "**/*.onnx.json", "**/*.pt", "**/*.pth"],
)
hiddenimports += collect_submodules("pynput.keyboard")
hiddenimports += collect_submodules(
    "piper",
    filter=lambda module: not module.startswith(
        ("piper.train", "piper.http_server", "piper.patch_voice_with_alignment")
    ),
)
hiddenimports += ["piper", "faster_whisper", "onnxruntime"]
excludes = ["torch", "torchvision", "torchaudio", "onnx"]

analysis = Analysis(
    [str(ROOT / "packaging" / "gui_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="DivyarajAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "packaging" / "divyaraj.ico"),
)
COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DivyarajAssistant",
)
