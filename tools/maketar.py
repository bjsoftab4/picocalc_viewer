#! /usr/bin/env python3

import subprocess
import sys
import os
import shutil

args = sys.argv
if len(sys.argv) < 2:
    print("Usage: python maketar.py <input_file> ... ")
    sys.exit(1)


def analyze_mp4(input_file):
    try:
        # ffprobe を実行して出力を取得
        result = subprocess.run(
            ["ffprobe", "-i", input_file, "-show_streams"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # 標準エラー出力を無視
            text=True
        )
    except FileNotFoundError:
        print("ffprobe が見つかりません。ffmpeg がインストールされているか確認してください。")
        return None
    
    # 出力から display_aspect_ratio を含む行を抽出
    aspect = None
    wxh = None
    sample_rate = None
    
    for line in result.stdout.splitlines():
        line = line.strip()
        key, dummy, val = line.partition('=')
        if key == "display_aspect_ratio":
            if val == "16:9":
                aspect = "320x180"
            elif val == "4:3":
                aspect = "320x240"
        if key == "width":
            width = int(val)
        if key == "height":
            height = int(val)
        if key == "sample_rate":
            sample_rate = int(val)
    if aspect is None:
        if width != None and height != None:
            w1 = width / 320
            h1 = height / w1
            if h1 <= 200:
                aspect="320x180"
            else:
                aspect="320x240"
    if aspect is None:
        print("Aspect is not defined")
        exit()
    if sample_rate >= 44100:
        sample_rate = sample_rate // 2
    
    print(input_file, aspect, str(sample_rate))
    return (aspect, str(sample_rate))

    
def cleartmpdir(tmpdir="/tmp/wk.mp4"):
    try:
        shutil.rmtree(tmpdir)
    except:
        pass
    os.makedirs(tmpdir)


tmpbasedir = "/tmp/mp4"
fps = 12
mp3bitrate=80000
jpgquarity=9   # lesser is good

for input_file in args[1:]:
    output_file = input_file.rpartition(".")[0]
    tmpoutdir = str(fps) # or output_file
    tmpdir = tmpbasedir+"/"+tmpoutdir
    cleartmpdir(tmpdir)
    rc = analyze_mp4(input_file)
    if rc is None:
        break
    aspect, sr = rc

    print(f"Aspect={aspect}\nSamplerate={sr}\nFps={fps}")
    
    print("Writing JPEG")
    result = subprocess.run(
        ["ffmpeg", "-i", input_file, "-s", aspect, "-q:v", str(jpgquarity), "-r", str(fps), "-vcodec", "mjpeg", tmpdir+"/image_%05d.jpg"],
        stderr=subprocess.DEVNULL
    )

    print("Writing MP3")
    result = subprocess.run(
        ["ffmpeg", "-i", input_file, "-ab", str(mp3bitrate), "-ar", sr, "-ac", "2", "-bits_per_raw_sample", "16", "-acodec", "mp3", "-y", output_file+".mp3"],
        stderr=subprocess.DEVNULL
    )

    cwd = os.getcwd()
    result = subprocess.run(
        ["tar", "cf", cwd+"/"+output_file+".tar", output_file+".mp3"],
        capture_output=True, text=True
    )

    os.chdir(tmpbasedir)
    result = subprocess.run(
        ["tar", "rf", cwd+"/"+output_file+".tar", "--sort=name", tmpoutdir],
        capture_output=True, text=True
    )
    os.chdir(cwd)

    # Create index
    """
    indexfile 
    line1: MP3 file size / filename 
    line2: 0 /  directory named fps / tarheader
    line3: jpgfile on 1min   offset from tarheader
    linex: not jpgfile  filesize / filename
    """
    result = subprocess.run(
        ["tar", "tvf", output_file+".tar"],
        capture_output=True, text=True
    )
    lines = result.stdout
    count=0
    total = 0
    with open(output_file+".idx", "w", encoding="utf-8") as f:
        for line in lines.splitlines():
            words = line.split()
            fname = words[5]
            size = int(words[2])
            if fname.endswith("/"):
                total = 0

            if fname.endswith((".jpg", ".JPG")):
                if count % (fps * 10) == 0: # write every 10 seconds
                    f.write(str(total)+" "+fname+"\n")
                count += 1
            else:
                f.write(words[2]+" "+fname+"\n")
            total += 512 + (size + 511)//512 * 512
        f.write(str(total)+" EOF\n\n")
    # Create tar file again
    result = subprocess.run(
        ["tar", "cf", cwd+"/"+output_file+".tar", output_file+".idx"],
        capture_output=True, text=True
    )
    result = subprocess.run(
        ["tar", "rf", cwd+"/"+output_file+".tar", output_file+".mp3"],
        capture_output=True, text=True
    )

    os.chdir(tmpbasedir)
    result = subprocess.run(
        ["tar", "rf", cwd+"/"+output_file+".tar", "--sort=name", tmpoutdir],
        capture_output=True, text=True
    )
    os.chdir(cwd)

