# micropython for picocalc with JPEGDEC, Adafruit_MP3
- bitbank2/JPEGDEC を使用して、picocalc で jpeg　画像を表示する。
- adafruit/Adafruit_MP3 を使用して、picocalc で MP3 を再生する。
- 上記を併用して、picocalc で音声付き動画を再生する。

zenodante/PicoCalc-micropython-driver を大幅に改造しているので、原本を fork したものとは別のリポジトリにしている。


## buildの前提

bitbank2/JPEGDEC は以下のディレクトリ構成に合わせて clone しておくこと

```
  picocalc_viewer/		this repository
      sound/			MP3 decoder / PCM driver
      jpegdec/			Interface to JPEGDEC
      picocalcdisplay/	modified copy of zenodante/PicoCalc-micropython-driver
      vtterminal/		copy of zenodante/PicoCalc-micropython-driver
      pico_files/		copy of zenodante/PicoCalc-micropython-driver
      rootfs/			python programs that are placed into rootfs
      sample/			sample files
      tools/			tools ( mp4 to tar converter )
      
  JPEGDEC/			    bitbank2/JPEGDEC
```

### ビルド手順

pico_files/modules のファイルをmicropython ビルド環境にコピー（micropython/ports/rp2/modules）

以下のコマンドでビルド
```sh
cd micropython/ports/rp2
make USER_C_MODULES="Path/To/picocalc_viewer/micropython.cmake" \
  BOARD=RPI_PICO2_W
```

ファームウェアを書き込んだ後に rootfs/ 全ファイルをFLASHファイルシステムへコピーする


## 配布ファイル説明

- ビルド済みファームウェア　FLASHファイルシステム部分はありません。FLASHファイルシステムありの公式ファームをまず書き込んでください。
  - picocalc-micropython-movieplayer-NOFLASH.uf2    JPEG decoder + MP3 decoder + movie player
  - picocalc-micropython-sound-NOFLASH.uf2          JPEG decoder + MP3 decoder （古い）
  - picocalc-micropython-jpegdec-NOFLASH.uf2        JPEG decoder （古い） 

- rootfs\
  boot.py 公式ファームは書き変え不可だったが、修正を簡易にするため外部に出した。\
  その他.py 実行に必要なpythonプログラム

- sample\
  サンプルの動画ファイル
  - countdown.tar\
    カウントダウン表示（フリー素材）
  - sig.......tar\
    とある動画のモーション部分（再利用可となっているので配布）
  - copyright.txt\
    動画の出典
  - CLOCK.tar\
    動画の音声同期確認用（自作

- rootfs
  - view.py\
再生表示するpythonプログラム\
import view し view.run() で起動します  picocalcのキーを何か押してスキップ。q キーで終了。\
前記の tar ファイルを /sd から読み込む設定にしています。

  - slide.py\
SDファイル内の jpeg ファイルを連続再生するプログラム　画面より大きければ縮小する。

  - mp3.py\
   MP3 ファイルを再生するプログラム。/sd フォルダに入っているMP3ファイルを検索して再生する。\
   n で次の曲。p で前の曲。他のキーで次の曲。\
   shift + n で次のフォルダ、shift + p で前のフォルダ\
   q で終了。\
   import mp3 し mp3.run() で起動します  mp3.run("/sd/hogehoge") でフォルダ指定可能。

  - mj.py\
音声付きで動画再生するプログラム　操作はmp3.pyと同等


- tools
  - maketar.py\
    指定した *.mp4 ファイルをA/V 分離し、JPEG変換、mp3変換し、 *.tar にまとめるプログラム

