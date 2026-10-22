"""Configurer les sondes de codecs sans masquer un problème audio réel."""
import os
import unittest
from unittest.mock import patch

from audio_configuration import configure_audio_backend


class AudioConfigurationTests(unittest.TestCase):
    def test_windows_excludes_video_encoders_and_preserves_diagnostic_settings(self):
        with patch('audio_configuration.sys.platform', 'win32'), patch.dict(os.environ, {}, clear=True):
            os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.*=true'
            configure_audio_backend()
            self.assertEqual(os.environ['QT_FFMPEG_EXCLUDE_ENCODERS'], 'av1_mf,h264_mf,hevc_mf')
            self.assertEqual(os.environ['QT_LOGGING_RULES'], 'qt.multimedia.*=true')
            self.assertNotIn('QT_MEDIA_BACKEND', os.environ)
            self.assertNotIn('QT_FFMPEG_DECODING_HW_DEVICE_TYPES', os.environ)

    def test_existing_exclusions_survive_repeated_configuration(self):
        with patch('audio_configuration.sys.platform', 'win32'), patch.dict(os.environ, {}, clear=True):
            os.environ['QT_FFMPEG_EXCLUDE_ENCODERS'] = ' custom_encoder, H264_MF '
            configure_audio_backend()
            first = os.environ['QT_FFMPEG_EXCLUDE_ENCODERS']
            configure_audio_backend()
            self.assertEqual(os.environ['QT_FFMPEG_EXCLUDE_ENCODERS'], first)
            self.assertEqual(first, 'custom_encoder,h264_mf,av1_mf,hevc_mf')

    def test_other_platform_does_not_change_environment(self):
        with patch('audio_configuration.sys.platform', 'linux'), patch.dict(os.environ, {}, clear=True):
            configure_audio_backend()
            self.assertNotIn('QT_FFMPEG_EXCLUDE_ENCODERS', os.environ)
