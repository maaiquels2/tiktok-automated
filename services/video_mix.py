
"""Concatenate / trim campaign MP4 clips into one ~15s 9:16 video via ffmpeg."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_FFMPEG = r"""C:\\Users\\Admin\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-9.0.1-full_build\\bin\\ffmpeg.exe"""


def find_ffmpeg() -> str:
    env = (os.environ.get("FFMPEG_PATH") or "").strip()
    if env and Path(env).is_file():
        return env
    which = shutil.which("ffmpeg")
    if which:
        return which
    if Path(DEFAULT_FFMPEG).is_file():
        return DEFAULT_FFMPEG
    raise FileNotFoundError(
        "ffmpeg nao encontrado. Instale o FFmpeg ou defina FFMPEG_PATH."
    )


def mix_clips(
    sources: list[tuple[Path, float]],
    destination: Path,
    *,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Take (path, seconds_from_start) clips, scale to 9:16, concat into destination."""
    if len(sources) < 2:
        raise ValueError("Precisa de pelo menos 2 clips.")
    if any(sec <= 0.05 for _, sec in sources):
        raise ValueError("Cada clip precisa de duracao positiva.")
    ffmpeg = find_ffmpeg()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fabrica-mix-") as tmp:
        tmp_path = Path(tmp)
        parts: list[Path] = []
        for idx, (src, seconds) in enumerate(sources):
            if not src.is_file():
                raise FileNotFoundError(f"Clip ausente: {src}")
            part = tmp_path / f"part-{idx:02d}.mp4"
            # trim + scale/pad to 9:16, mute-safe audio or generate silent if missing
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
            )
            cmd = [
                ffmpeg, "-y",
                "-ss", "0",
                "-t", f"{seconds:.3f}",
                "-i", str(src),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-ar", "44100", "-ac", "2",
                "-shortest",
                "-movflags", "+faststart",
                str(part),
            ]
            # If source has no audio, ffmpeg may fail with -c:a aac; retry with anullsrc
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                cmd_silent = [
                    ffmpeg, "-y",
                    "-ss", "0",
                    "-t", f"{seconds:.3f}",
                    "-i", str(src),
                    "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-movflags", "+faststart",
                    str(part),
                ]
                proc2 = subprocess.run(cmd_silent, capture_output=True, text=True)
                if proc2.returncode != 0:
                    err = (proc.stderr or "")[-1200:] + "\n" + (proc2.stderr or "")[-1200:]
                    raise RuntimeError(f"ffmpeg falhou no clip {idx+1}: {err}")
            parts.append(part)

        list_file = tmp_path / "list.txt"
        list_file.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in parts),
            encoding="utf-8",
        )
        out_tmp = tmp_path / "out.mp4"
        concat = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out_tmp),
        ]
        proc = subprocess.run(concat, capture_output=True, text=True)
        if proc.returncode != 0:
            # re-encode concat fallback
            concat2 = [
                ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(out_tmp),
            ]
            proc2 = subprocess.run(concat2, capture_output=True, text=True)
            if proc2.returncode != 0:
                raise RuntimeError(
                    "ffmpeg falhou ao juntar os clips:\n"
                    + (proc.stderr or "")[-800:]
                    + "\n"
                    + (proc2.stderr or "")[-800:]
                )
        shutil.copyfile(out_tmp, destination)
    return destination
