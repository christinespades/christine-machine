# This module is for everything video. mp4, mov, avi, etc.. decode, encode, upscale, compress, etc..

# below is just some ffmpeg, mp4 compressor
import os
import sys
import subprocess
import threading
import time
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

VBR_TARGET_BITRATE = "7M"
VBR_MAX_ALLOWED_BITRATE = "13M"
PRESET = "slow"
FRAME_RATE = "120"
MAX_CONCURRENT_JOBS = 4

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
WORK_DIR = Path(r"G:\ytck")
OUTPUT_SUFFIX = "_comp.mp4"
LOG_FREQUENCY = 10

COMPLETED_COUNT = 0
CNT_MTX = threading.Lock()

def LG(msg):
    tstmp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{tstmp} {msg}")

def GtFSiz(file_path):
    return round(Path(file_path).stat().st_size / (1024 * 1024), 2)

def CmprsV(input_file, index, totFs):
    global COMPLETED_COUNT
    iPth = Path(input_file)
    oF = WORK_DIR / (iPth.stem + OUTPUT_SUFFIX)

    with CNT_MTX:
        LG(f"[START] {iPth.name} ({index}/{totFs})")

    if oF.exists():
        LG(f"[SKIP] Output already exists: {oF.name}")
        with CNT_MTX:
            COMPLETED_COUNT += 1
        return

    codec = GtVCodc(iPth)
    if codec == "h264":
        decode_flag = "h264_cuvid"
    else:
        decode_flag = "hevc_cuvid"

    gpu_cmd_vbr = [
        FFMPEG_PATH,
        "-hwaccel", "cuda",
        "-c:v", decode_flag, # hevc_cuvid if H.265, h264_cuvid if H.264 input
        "-i", str(iPth),
        "-c:v", "hevc_nvenc",
        "-preset", PRESET,
        "-rc", "vbr",
        "-b:v", VBR_TARGET_BITRATE,
        "-maxrate", VBR_MAX_ALLOWED_BITRATE,
        "-r", FRAME_RATE,
        "-c:a", "copy",
        "-y", str(oF)
    ]
    LG(f"[COM] {input_file.name} → {oF.name}")

    comp_proc = subprocess.run(gpu_cmd_vbr, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if comp_proc.returncode != 0:
        if oF.exists():
            try:
                os.remove(oF)
            except Exception as e:
                LG(f"[WARN] Could not remove partial output file {oF.name}: {e}")

        LG(f"[ERR] Compression failed for {iPth.name}")
        LG(f"[ERR] STDOUT: {comp_proc.stdout}")
        LG(f"[ERR] STDERR: {comp_proc.stderr}")

        with CNT_MTX:
            COMPLETED_COUNT += 1
        raise RuntimeError(f"Compression error on {iPth.name}")
    else:
        original_size = GtFSiz(iPth)
        compressed_size = GtFSiz(oF)
        reduction = 0
        if original_size > 0:
            reduction = round(((original_size - compressed_size) / original_size) * 100, 2)
        LG(f"[DONE] {iPth.name}: {original_size} MB → {compressed_size} MB (-{reduction}%)")

    if input_file.exists():
        try:
            os.remove(input_file)
        except Exception as e:
            LG(f"[WARN] Could not remove original file {input_file.name}: {e}")

    with CNT_MTX:
        COMPLETED_COUNT += 1

def GtProg(totFs, start_time):
    global COMPLETED_COUNT

    with tqdm(total=totFs, unit='file', ncols=80,
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
        lCnt = 0
        while True:
            time.sleep(LOG_FREQUENCY)
            with CNT_MTX:
                curCnt = COMPLETED_COUNT

            if curCnt >= totFs:
                break

            pbar.update(curCnt - lCnt)
            lCnt = curCnt

    elapsed = time.time() - start_time
    LG(f"[PROG] Completed {totFs} in {elapsed:.2f} seconds.")

def GtVCodc(iPth):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "csv=p=0",
        str(iPth)
    ]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return output.strip().lower()  # e.g. "h264" or "hevc"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e}")

    codec = output.strip().lower()
    if not codec:
        raise RuntimeError("Could not detect video codec.")
    if codec not in ("h264", "hevc", "h265"):
        raise RuntimeError(f"Unsupported codec detected: {codec}")
    return codec

if __name__ == "__main__":
    LG("\n" * 4)

    video_files = sorted(
        [f for f in WORK_DIR.iterdir()
         if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi"]],
        key=lambda f: f.name.lower()
    )
    if not video_files:
        LG("[INF] No valid video files found.")
        sys.exit(0)

    totFs = len(video_files)
    start_time = time.time()

    prog_thread = threading.Thread(
        target=GtProg,
        args=(totFs, start_time),
        daemon=True
    )
    prog_thread.start()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as executor:
        futures = []
        for i, f in enumerate(video_files, start=1):
            fut = executor.submit(CmprsV, f, i, totFs)
            futures.append(fut)

        try:
            for fut in as_completed(futures):
                fut.result()
        except Exception as e:
            LG(f"[FATAL] {e}")
            for f in futures:
                f.cancel()
            executor.shutdown(cancel_futures=True)
            sys.exit(1)
    prog_thread.join()

    with CNT_MTX:
        done = COMPLETED_COUNT
    remaining = totFs - done
    LG(f"[DONE] Processed {done} files, {remaining} left unprocessed.")
