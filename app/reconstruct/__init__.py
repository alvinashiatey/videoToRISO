"""
RISO-to-Video Reconstruction Module

This module provides tools for scanning printed RISO contact sheets
and reconstructing them back into video files, preserving the unique
RISO aesthetic.

Based on the algorithm concepts from:
- Ostromoukhov & Hersch's image processing research
- Standard grid detection and computer vision techniques
"""

from .scanner import ScanProcessor
from .grid_detect import GridDetector
from .extractor import FrameExtractor
from .assembler import VideoAssembler
from .metadata import MetadataEncoder, MetadataDecoder

__all__ = [
    'ScanProcessor',
    'GridDetector',
    'FrameExtractor',
    'VideoAssembler',
    'MetadataEncoder',
    'MetadataDecoder'
]
