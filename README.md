#micropython for picocalc with JPEGDEC
bitbank2/JPEGDEC ���g�p���āApicocalc �� jpeg�f�R�[�_��ǉ�����B

zenodante/PicoCalc-micropython-driver ��啝�ɉ������Ă���̂ŁA���{�� fork �������̂Ƃ͕ʂ̃��|�W�g���ɂ���


#build�̑O��

bitbank2/JPEGDEC �͈ȉ��̃f�B���N�g���\���ɍ��킹�� clone ���Ă�������

```
  picocalc_viewer/		this repository
      jpegdec/			Interface to JPEGDEC
      picocalcdisplay/	modified copy of zenodante/PicoCalc-micropython-driver
      vtterminal/		copy of zenodante/PicoCalc-micropython-driver
      pico_files/		copy of zenodante/PicoCalc-micropython-driver
  JPEGDEC/			    bitbank2/JPEGDEC
```

##�r���h�菇

pico_files/modules �̃t�@�C����micropython �r���h���ɃR�s�[�imicropython/ports/rp2/modules�j

�ȉ��̃R�}���h�Ńr���h
```sh
cd micropython/ports/rp2
make USER_C_MODULES="Path/To/picocalc_viewer/micropython.cmake" \
  BOARD=[TARGET_BOARD]
```

����m�F���� `TARGET_BOARD` ��
- `RPI_PICO2_W`

�Ō�� boot.py ���t�@�C���V�X�e���փR�s�[


#�z�z�t�@�C������

picocalc-micropython-jpegdec-NOFLASH.uf2  �t�@�[���E�F�A ROMFS �����͂���܂���BROMFS����̌����t�@�[�����܂���������ł��������B

boot.py �����ł̓t�@�[���ɏ������ݍς݂��������A�C�����ȈՂɂ��邽�ߊO���ɏo�����B

countdown.tar  �J�E���g�_�E���\���i�t���[�f�ށj\
sig.......tar  �Ƃ��铮��̃��[�V���������i�ė��p�ƂȂ��Ă���̂Ŕz�z�j

view.py  �Đ��\������t�@�C��  import view �� view.run() �ŋN�����܂�

