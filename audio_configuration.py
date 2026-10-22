"""Configurer Qt Multimedia avant sa première initialisation audio.

Qt/FFmpeg énumère aussi les encodeurs lors de la création du lecteur musical.
Sous Windows, tester les encodeurs vidéo Media Foundation provoque des messages
MFT sans rapport avec l'AAC lu par Bifurk. Le filtre Qt les exclut AVANT leur
ouverture, sans filtrer les journaux ni changer le décodage audio.

Mécanisme vérifié dans QFFmpeg::CodecStoreSingleton (Qt 6.12) :
https://github.com/qt/qtmultimedia/blob/6.12/src/plugins/multimedia/ffmpeg/qffmpegcodecstorage.cpp
QT_FFMPEG_EXCLUDE_ENCODERS est une option interne : la revérifier lors d'une
mise à jour majeure de Qt. Une version antérieure qui l'ignore continue à lire
normalement la musique mais peut conserver les diagnostics de codecs vidéo.
"""
import os
import sys


VIDEO_ENCODERS_UNUSED = ('av1_mf', 'h264_mf', 'hevc_mf')


def configure_audio_backend():
    """Écarter les sondes vidéo Windows, en conservant les exclusions de l'utilisateur.

    Appeler avant SoundBank/QMediaPlayer : Qt ne lit cette liste qu'une fois.
    Les autres plateformes, décodeurs, volumes et règles de journalisation restent
    inchangés. L'appel répété n'ajoute pas de doublons.
    """
    if sys.platform != 'win32':
        return
    variable = 'QT_FFMPEG_EXCLUDE_ENCODERS'
    encoders = [name.strip().lower() for name in os.environ.get(variable, '').split(',') if name.strip()]
    os.environ[variable] = ','.join(dict.fromkeys([*encoders, *VIDEO_ENCODERS_UNUSED]))
