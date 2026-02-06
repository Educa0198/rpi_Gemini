from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Optional

import RPi.GPIO as GPIO


class LEDState(Enum):
    OFF = 0
    SETTING_UP_BT = 1            # Blue blinking
    READY_TO_CONNECT = 2         # Blue solid
    PAIRED = 3           # Green blinking (connected but not sending MACs)
    SENDING_MACS = 4             # Green solid
    ERROR = 5                    # Red solid
    IDLE_AFTER_SENDING = 6       # Yellow (red + green on) when it was sending before and then stopped


class LEDManager:
    """Background LED controller for Raspberry Pi.

    Pinout uses BCM numbering by default:
      - green_pin (GPIO 5)
      - blue_pin  (GPIO 6)
      - red_pin   (GPIO 12)

    States are controlled via set_state(). Call start() once before use and
    stop() before exiting the program to clean up GPIO resources.
    """

    def __init__(
        self,
        *,
        green_pin: int = 5,
        blue_pin: int = 6,
        red_pin: int = 12,
        blink_interval_seconds: float = 0.5,
    ) -> None:
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        self.red_pin = red_pin
        self.blink_interval_seconds = blink_interval_seconds

        self._state_lock = threading.Lock()
        self._state: LEDState = LEDState.OFF
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        # Ensure deterministic startup states to avoid faint LED glow
        GPIO.setup(self.green_pin, GPIO.OUT)
        GPIO.setup(self.blue_pin, GPIO.OUT)
        GPIO.setup(self.red_pin, GPIO.OUT)
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="LEDManagerThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._all_off()
        # Note: We intentionally do not call GPIO.cleanup() here to avoid
        # interfering with other processes/threads that may also be using
        # RPi.GPIO simultaneously. The process that owns overall GPIO lifecycle
        # should call cleanup on program exit.

    def set_state(self, new_state: LEDState) -> None:
        with self._state_lock:
            self._state = new_state

    def _get_state(self) -> LEDState:
        with self._state_lock:
            return self._state

    def _all_off(self) -> None:
        GPIO.output(self.green_pin, GPIO.LOW)
        GPIO.output(self.blue_pin, GPIO.LOW)
        GPIO.output(self.red_pin, GPIO.LOW)

    def _run_loop(self) -> None:
        # Ensure LEDs start off
        self._all_off()
        while self._running:
            state = self._get_state()

            if state == LEDState.OFF:
                self._all_off()
                time.sleep(0.1)
                continue

            if state == LEDState.SETTING_UP_BT:
                # Blue blinking
                GPIO.output(self.red_pin, GPIO.LOW)
                GPIO.output(self.green_pin, GPIO.LOW)
                GPIO.output(self.blue_pin, GPIO.HIGH)
                time.sleep(self.blink_interval_seconds)
                GPIO.output(self.blue_pin, GPIO.LOW)
                time.sleep(self.blink_interval_seconds)
                continue

            if state == LEDState.READY_TO_CONNECT:
                # Blue solid
                GPIO.output(self.green_pin, GPIO.LOW)
                GPIO.output(self.red_pin, GPIO.LOW)
                GPIO.output(self.blue_pin, GPIO.HIGH)
                time.sleep(0.1)
                continue

            if state == LEDState.PAIRED:
                # Green blinking
                GPIO.output(self.red_pin, GPIO.LOW)
                GPIO.output(self.blue_pin, GPIO.LOW)
                GPIO.output(self.green_pin, GPIO.HIGH)
                time.sleep(self.blink_interval_seconds)
                GPIO.output(self.green_pin, GPIO.LOW)
                time.sleep(self.blink_interval_seconds)
                continue

            if state == LEDState.SENDING_MACS:
                # Green solid
                GPIO.output(self.blue_pin, GPIO.LOW)
                GPIO.output(self.red_pin, GPIO.LOW)
                GPIO.output(self.green_pin, GPIO.HIGH)
                time.sleep(0.1)
                continue

            if state == LEDState.ERROR:
                # Red solid
                GPIO.output(self.green_pin, GPIO.LOW)
                GPIO.output(self.blue_pin, GPIO.LOW)
                GPIO.output(self.red_pin, GPIO.HIGH)
                time.sleep(0.1)
                continue

            if state == LEDState.IDLE_AFTER_SENDING:
                # Yellow = Red + Green solid
                GPIO.output(self.blue_pin, GPIO.LOW)
                GPIO.output(self.green_pin, GPIO.HIGH)
                GPIO.output(self.red_pin, GPIO.HIGH)
                time.sleep(0.1)
                continue


