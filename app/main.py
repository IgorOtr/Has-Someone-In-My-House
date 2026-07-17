"""Application entry point and main monitoring loop.

This module only orchestrates the specialized components; it does not
implement detection, tracking, cooldown or persistence logic itself.
"""

from __future__ import annotations

import logging
import time
from typing import List

import cv2
import numpy as np

from app.alert_recorder import AlertRecorder
from app.camera import Camera, CameraError
from app.capture_controller import CaptureController
from app.config import ConfigError, load_config
from app.detection_tracker import DetectionTracker
from app.detector import InferenceError, PersonDetector
from app.image_manager import ImageManager
from app.logging_config import configure_logging
from app.models import Detection

logger = logging.getLogger(__name__)

WINDOW_NAME = "Person Detection Monitor"
QUIT_KEY = ord("q")

STATUS_MONITORING = "Monitoring"
STATUS_PERSON_DETECTED = "Person detected"
STATUS_DETECTION_CONFIRMED = "Detection confirmed"
STATUS_IMAGE_SAVED = "Image saved"
STATUS_COOLDOWN = "Cooldown"
STATUS_CAMERA_ERROR = "Camera error"
STATUS_INFERENCE_ERROR = "Inference error"
STATUS_SAVE_ERROR = "Save error"

_PREVIEW_BOX_COLOR = (0, 220, 0)
_HUD_COLOR = (255, 255, 255)
_HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _draw_preview_boxes(frame: np.ndarray, detections: List[Detection]) -> None:
    for detection in detections:
        cv2.rectangle(
            frame,
            (detection.x1, detection.y1),
            (detection.x2, detection.y2),
            _PREVIEW_BOX_COLOR,
            2,
        )
        label = f"{detection.confidence:.2f}"
        cv2.putText(
            frame,
            label,
            (detection.x1, max(detection.y1 - 8, 12)),
            _HUD_FONT,
            0.5,
            _PREVIEW_BOX_COLOR,
            2,
            cv2.LINE_AA,
        )


def _build_alert_message(detections: List[Detection]) -> str:
    person_count = len(detections)
    highest_confidence = max((d.confidence for d in detections), default=0.0)
    plural = "s" if person_count != 1 else ""
    return (
        f"Pessoa detectada ({person_count} pessoa{plural}, "
        f"confiança máxima {highest_confidence:.0%})"
    )


def _draw_hud(
    frame: np.ndarray,
    status: str,
    fps: float,
    device: str,
    person_count: int,
    cooldown_remaining: float,
) -> None:
    lines = [
        f"Status: {status}",
        f"FPS: {fps:.1f}  Device: {device.upper()}",
        f"People detected: {person_count}",
    ]
    if cooldown_remaining > 0:
        lines.append(f"Cooldown: {cooldown_remaining:.0f}s")

    for index, line in enumerate(lines):
        y = frame.shape[0] - 15 - (len(lines) - 1 - index) * 22
        cv2.putText(frame, line, (10, y), _HUD_FONT, 0.55, _HUD_COLOR, 1, cv2.LINE_AA)


def run() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Invalid configuration: {exc}")
        return

    configure_logging(config.log_level)
    logger.info("Application started")
    logger.info(
        "Configuration loaded (camera=%s, model=%s, confidence=%.2f, "
        "capture_delay=%.1fs, cooldown=%.0fs)",
        config.camera_index,
        config.model_path,
        config.confidence_threshold,
        config.capture_delay_seconds,
        config.capture_cooldown_seconds,
    )

    image_manager = ImageManager(
        image_directory=config.image_directory,
        image_format=config.image_format,
        jpeg_quality=config.image_jpeg_quality,
        retention_hours=config.image_retention_hours,
    )
    image_manager.cleanup_expired_images()

    detector = PersonDetector(
        model_path=config.model_path,
        image_size=config.model_image_size,
        confidence_threshold=config.confidence_threshold,
    )
    tracker = DetectionTracker(
        window_size=config.detection_window_size,
        minimum_positive_frames=config.minimum_positive_frames,
    )
    capture_controller = CaptureController(
        cooldown_seconds=config.capture_cooldown_seconds,
        capture_delay_seconds=config.capture_delay_seconds,
    )
    camera = Camera(
        index=config.camera_index,
        width=config.camera_width,
        height=config.camera_height,
    )
    alert_recorder = AlertRecorder.create()

    cleanup_interval_seconds = config.image_cleanup_interval_minutes * 60
    last_cleanup_time = time.monotonic()

    frame_index = 0
    last_detections: List[Detection] = []
    status = STATUS_MONITORING
    fps = 0.0
    prev_frame_time = time.monotonic()
    window_created = False

    try:
        camera.open()
        logger.info(
            "Webcam initialized (index=%s, resolution=%sx%s)",
            config.camera_index,
            config.camera_width,
            config.camera_height,
        )
        cv2.namedWindow(WINDOW_NAME)
        window_created = True

        while True:
            try:
                frame = camera.read_frame()
            except CameraError as exc:
                logger.error("Webcam error: %s", exc)
                status = STATUS_CAMERA_ERROR
                break

            frame_index += 1
            now = time.monotonic()
            elapsed = now - prev_frame_time
            prev_frame_time = now
            if elapsed > 0:
                instantaneous_fps = 1.0 / elapsed
                fps = instantaneous_fps if fps == 0 else (fps * 0.9 + instantaneous_fps * 0.1)

            if frame_index % config.process_every_n_frames == 0:
                try:
                    last_detections = detector.detect(frame)
                except InferenceError as exc:
                    logger.error("Inference error: %s", exc)
                    status = STATUS_INFERENCE_ERROR
                    last_detections = []
                else:
                    person_present = len(last_detections) > 0
                    tracker.update(person_present)
                    if person_present:
                        logger.debug("Person detected in current frame")
                        status = STATUS_PERSON_DETECTED
                    else:
                        status = STATUS_MONITORING

            if tracker.is_confirmed():
                status = STATUS_DETECTION_CONFIRMED
                capture_controller.notify_detection_confirmed()
                if capture_controller.is_capture_due():
                    logger.info("Detection confirmed, saving image")
                    saved_path = image_manager.save_detection_image(frame, last_detections)
                    if saved_path is not None:
                        capture_controller.notify_saved()
                        tracker.reset()
                        status = STATUS_IMAGE_SAVED
                        logger.info("Image saved, ready for next detection")
                        alert_recorder.record_alert(
                            _build_alert_message(last_detections), saved_path
                        )
                    else:
                        status = STATUS_SAVE_ERROR
                elif not capture_controller.can_capture():
                    status = STATUS_COOLDOWN
            else:
                capture_controller.cancel_pending_capture()

            if now - last_cleanup_time >= cleanup_interval_seconds:
                image_manager.cleanup_expired_images()
                last_cleanup_time = now

            display_frame = frame.copy()
            _draw_preview_boxes(display_frame, last_detections)
            _draw_hud(
                display_frame,
                status=status,
                fps=fps,
                device=detector.device,
                person_count=len(last_detections),
                cooldown_remaining=capture_controller.cooldown_remaining_seconds(),
            )
            cv2.imshow(WINDOW_NAME, display_frame)

            if cv2.waitKey(1) & 0xFF == QUIT_KEY:
                logger.info("Quit key pressed, shutting down")
                break

    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
    except Exception:
        logger.exception("Unexpected error in main loop")
    finally:
        camera.release()
        if window_created:
            cv2.destroyAllWindows()
        logger.info("Application terminated")
