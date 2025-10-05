#micropython for picocalc with JPEGDEC
bitbank2/JPEGDEC を使用して、picocalc に jpegデコーダを追加する。

zenodante/PicoCalc-micropython-driver を大幅に改造しているので、原本を fork したものとは別のリポジトリにした


#buildの前提

bitbank2/JPEGDEC は以下のディレクトリ構成に合わせて clone しておくこと

```
  picocalc_viewer/		this repository
      jpegdec/			Interface to JPEGDEC
      picocalcdisplay/	modified copy of zenodante/PicoCalc-micropython-driver
      vtterminal/		copy of zenodante/PicoCalc-micropython-driver
      pico_files/		copy of zenodante/PicoCalc-micropython-driver
  JPEGDEC/			    bitbank2/JPEGDEC
```

##ビルド手順

pico_files/modules のファイルをmicropython ビルド環境にコピー（micropython/ports/rp2/modules）

以下のコマンドでビルド
```sh
cd micropython/ports/rp2
make USER_C_MODULES="Path/To/picocalc_viewer/micropython.cmake" \
  BOARD=[TARGET_BOARD]
```

動作確認した `TARGET_BOARD` は
- `RPI_PICO2_W`

最後に boot.py をファイルシステムへコピー


#配布ファイル説明

picocalc-micropython-jpegdec-NOFLASH.uf2  ファームウェア ROMFS 部分はありません。ROMFSありの公式ファームをまず書き込んでください。

boot.py 公式ではファームに書き込み済みだったが、修正を簡易にするため外部に出した。

countdown.tar  カウントダウン表示（フリー素材）\
sig.......tar  とある動画のモーション部分（再利用可となっているので配布）

view.py  再生表示するファイル  import view し view.run() で起動します

