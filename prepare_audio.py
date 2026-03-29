"""
prepare_audio.py

Step 1 - Download raw evaluation outputs from IRCAM servers.
Step 2 - Cut and copy to website audio/ folders.

Usage:
    python prepare_audio.py --download
    python prepare_audio.py --process  (after reviewing raw_data/)
    python prepare_audio.py --download --process  (run both)
"""

import subprocess
import os
import json
import argparse
from pathlib import Path

# -- Servers ------------------------------------------------------------------
REACH1 = "karchkhadze@reach1.ircam.fr"
REACH2 = "karchkhadze@reach2.ircam.fr"
REMOTE_BASE = "/home/karchkhadze/musical-accompaniment-ldm/lightning_logs/streaming_eval_outputs"

# -- Sample indices for Track01877 --------------------------------------------
SAMPLE_INDICES = ["00004", "00005", "00006", "00007"]

# -- Folders to download: (server, remote_folder, local_name, model, condition)
EVAL_FOLDERS = [
    (REACH1, "Diff_latent_cond_gen_concat_r0.25_w-1",       "diff_retro",     "diffusion", "retro"),
    (REACH1, "Diff_latent_cond_gen_concat_r0.25_w0",        "diff_immediate", "diffusion", "immediate"),
    (REACH1, "Diff_latent_cond_gen_concat_r0.25_w1",        "diff_lookahead", "diffusion", "lookahead"),
    (REACH2, "CD_latent_cond_gen_concat_inpaint_r0.25_w-1", "cd_retro",       "cd",        "retro"),
    (REACH2, "CD_latent_cond_gen_concat_inpaint_r0.25_w0",  "cd_immediate",   "cd",        "immediate"),
    (REACH2, "CD_latent_cond_gen_concat_inpaint_r0.25_w1",  "cd_lookahead",   "cd",        "lookahead"),
]

# Files to pull from each sample folder (skip *_16000.wav and input_audio.wav)
FILES_TO_DOWNLOAD = [
    "metadata.json",
    "ground_truth/pred.wav",
    "ground_truth/mix.wav",
    "pred/pred.wav",
    "pred/mix.wav",
]

RAW_DATA_DIR = Path("raw_data")
AUDIO_DIR    = Path("audio")


# -----------------------------------------------------------------------------
# STEP 1: DOWNLOAD
# -----------------------------------------------------------------------------

def scp(server, remote_path, local_path):
    """Download a single file via scp. Skips if already exists locally."""
    local_path = Path(local_path)
    if local_path.exists():
        print(f"  skip  {local_path}")
        return True
    local_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["scp", f"{server}:{remote_path}", str(local_path)]
    print(f"  scp {remote_path.split('/')[-1]} -> {local_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        return False
    return True


def download():
    print("=" * 60)
    print("STEP 1: Downloading raw data from IRCAM servers")
    print("=" * 60)

    for server, remote_folder, local_name, model, condition in EVAL_FOLDERS:
        print(f"\n[{local_name}]  ({server})")
        remote_base = f"{REMOTE_BASE}/{remote_folder}/model_predictions"

        for idx in SAMPLE_INDICES:
            remote_sample = f"{remote_base}/{idx}"
            local_sample = RAW_DATA_DIR / local_name / idx

            for rel_file in FILES_TO_DOWNLOAD:
                remote_file = f"{remote_sample}/{rel_file}"
                local_file = local_sample / rel_file
                scp(server, remote_file, local_file)

    print("\nDownload complete. Raw data saved to:", RAW_DATA_DIR)
    _verify_metadata()


def _verify_metadata():
    """Print a summary table to sanity-check stems/tracks."""
    print("\n-- Metadata verification --")
    print(f"{'Folder':<20} {'Index':<8} {'Track':<12} {'Stem':<8} {'w':>4}")
    print("-" * 56)
    for _, _, local_name, _, _ in EVAL_FOLDERS:
        for idx in SAMPLE_INDICES:
            meta_path = RAW_DATA_DIR / local_name / idx / "metadata.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    m = json.load(f)
                print(f"{local_name:<20} {idx:<8} {m['track_id']:<12} {m['stem']:<8} {m['w']:>4}")
            else:
                print(f"{local_name:<20} {idx:<8} {'MISSING':<12}")


# -----------------------------------------------------------------------------
# STEP 2: PROCESS  (cut + copy to audio/ folders)
# -----------------------------------------------------------------------------

def process(start_sec=0, duration_sec=25):
    """
    Cut [start_sec : start_sec+duration_sec] from each downloaded wav
    and write to the website audio/ folder structure.

    Requires ffmpeg on PATH.

    Output layout:
      audio/original/{bass,drums,guitar,piano}.wav
      audio/diffusion/{retro,immediate,lookahead}/{bass,drums,guitar,piano}_gen.wav
      audio/diffusion/{retro,immediate,lookahead}/{bass,drums,guitar,piano}_mix.wav
      audio/cd/{retro,immediate,lookahead}/...
    """
    print("=" * 60)
    print(f"STEP 2: Processing - cutting {duration_sec}s from t={start_sec}s")
    print("=" * 60)

    # Ground truth stems: take from diff_retro (same GT regardless of condition)
    print("\n[Ground truth stems]")
    for idx in SAMPLE_INDICES:
        meta_path = RAW_DATA_DIR / "diff_retro" / idx / "metadata.json"
        if not meta_path.exists():
            print(f"  WARNING: missing metadata for index {idx}, skipping")
            continue
        with open(meta_path) as f:
            m = json.load(f)
        stem = m["stem"]
        src = RAW_DATA_DIR / "diff_retro" / idx / "ground_truth" / "pred.wav"
        dst = AUDIO_DIR / "original" / f"{stem}.wav"
        _ffmpeg_cut(src, dst, start_sec, duration_sec)

    # Generated stems and mixes
    for _, _, local_name, model, condition in EVAL_FOLDERS:
        print(f"\n[{local_name}]")
        for idx in SAMPLE_INDICES:
            meta_path = RAW_DATA_DIR / local_name / idx / "metadata.json"
            if not meta_path.exists():
                print(f"  WARNING: missing metadata for index {idx}, skipping")
                continue
            with open(meta_path) as f:
                m = json.load(f)
            stem = m["stem"]

            src_gen = RAW_DATA_DIR / local_name / idx / "pred" / "pred.wav"
            dst_gen = AUDIO_DIR / model / condition / f"{stem}_gen.wav"
            _ffmpeg_cut(src_gen, dst_gen, start_sec, duration_sec)

            src_mix = RAW_DATA_DIR / local_name / idx / "pred" / "mix.wav"
            dst_mix = AUDIO_DIR / model / condition / f"{stem}_mix.wav"
            _ffmpeg_cut(src_mix, dst_mix, start_sec, duration_sec)

    print("\nProcessing complete. Website audio files saved to:", AUDIO_DIR)


def _ffmpeg_cut(src, dst, start_sec, duration_sec):
    """Cut a wav with ffmpeg. Skips if src doesn't exist."""
    src, dst = Path(src), Path(dst)
    if not src.exists():
        print(f"  WARNING: source missing: {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", str(src),
        "-c", "copy",
        str(dst),
    ]
    print(f"  cut {src.name} -> {dst}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg failed: {result.stderr.strip()[-200:]}")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download raw data from servers")
    parser.add_argument("--process",  action="store_true", help="Cut and copy to website audio/ folders")
    parser.add_argument("--start",    type=float, default=0,  help="Cut start time in seconds (default: 0)")
    parser.add_argument("--duration", type=float, default=25, help="Cut duration in seconds (default: 25)")
    args = parser.parse_args()

    if not args.download and not args.process:
        parser.print_help()
    if args.download:
        download()
    if args.process:
        process(start_sec=args.start, duration_sec=args.duration)
