"""Webcam access encapsulated behind a small, testable interface."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Raised when the webcam cannot be opened or read from."""


class Camera:
    """Thin wrapper around ``cv2.VideoCapture``."""

    def __init__(self, index: int, width: int, height: int) -> None:
        self._index = index
        self._width = width
        self._height = height
        self._capture: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        """Open the webcam and configure its resolution.

        Raises:
            CameraError: If the device cannot be opened.
        """
        capture = cv2.VideoCapture(self._index)
        if not capture.isOpened():
            capture.release()
            raise CameraError(f"Unable to open webcam at index {self._index}.")

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._capture = capture

    def read_frame(self) -> np.ndarray:
        """Capture a single frame.

        Raises:
            CameraError: If the camera is not open or the frame could not
                be read.
        """
        if self._capture is None:
            raise CameraError("Camera is not open.")

        success, frame = self._capture.read()
        if not success or frame is None:
            raise CameraError("Failed to read frame from webcam.")
        return frame

    def get_resolution(self) -> Tuple[int, int]:
        if self._capture is None:
            raise CameraError("Camera is not open.")
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height

    def release(self) -> None:
        """Release the underlying capture device, if open."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()
