"""Convert all wav files in audio/ to mp3 and delete the wavs."""
import subprocess
import os
from pathlib import Path

audio_dir = Path("audio")
wavs = list(audio_dir.rglob("*.wav"))
print(f"Found {len(wavs)} wav files")

for wav in wavs:
    mp3 = wav.with_suffix(".mp3")
    cmd = ["ffmpeg", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        os.remove(wav)
        print(f"  converted {wav.name} -> {mp3.name}")
    else:
        print(f"  FAILED {wav.name}: {result.stderr[-100:]}")

print("Done.")
