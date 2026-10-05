"""
AegisFlow AI - Serial Transport
Abstracts physical serial implementation to allow simulation and testing without real COM ports.

Two concrete implementations:
  - DummySerialTransport : zero-hardware fake used by tests and offline simulation.
  - PySerialTransport    : production implementation backed by pyserial.
                           Supports Windows COMx and Linux /dev/ttyUSBx|/dev/ttyACMx.

WP15 NOTE — USB disconnect on Windows:
  On Windows, physically removing a USB-UART adapter does NOT immediately cause
  serial.Serial.is_open to return False.  The OS COM-port ghost can remain "open"
  for several seconds, and write() can silently succeed (bytes go nowhere).
  To detect true transport loss we track consecutive I/O failures.  After
  _MAX_IO_FAILURES consecutive write or read exceptions the transport is considered
  dead regardless of is_open, and disconnect() is called proactively.
"""

import abc
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Number of consecutive I/O failures before PySerialTransport self-disconnects
_MAX_IO_FAILURES = 3


class SerialTransport(abc.ABC):
    """Abstract base class for a serial connection to the hardware controller."""

    @abc.abstractmethod
    def connect(self) -> bool:
        """Open the serial connection. Returns True on success, False on failure."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close the serial connection cleanly."""

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Return True when the connection is open and ready for I/O."""

    @abc.abstractmethod
    def write_line(self, data: str) -> bool:
        """Write a single newline-terminated string. Returns True on success."""

    @abc.abstractmethod
    def read_line(self) -> Optional[str]:
        """Read one newline-terminated line. Returns None on timeout or error."""


# ---------------------------------------------------------------------------
# Dummy / offline transport (tests & simulation)
# ---------------------------------------------------------------------------

class DummySerialTransport(SerialTransport):
    """
    Fake transport for tests and offline simulation.
    All I/O is in-process; no file handles or COM ports are touched.
    """

    def __init__(self) -> None:
        self.connected: bool = False
        self.last_written: Optional[str] = None
        self.mock_responses: list = []
        # When set to True, write_line will always return False (simulate write fault)
        self.fail_writes: bool = False

    def connect(self) -> bool:
        self.connected = True
        logger.debug("DummySerialTransport: connected.")
        return True

    def disconnect(self) -> None:
        self.connected = False
        logger.debug("DummySerialTransport: disconnected.")

    def is_connected(self) -> bool:
        return self.connected

    def write_line(self, data: str) -> bool:
        if not self.connected or self.fail_writes:
            return False
        self.last_written = data
        return True

    def read_line(self) -> Optional[str]:
        if not self.connected:
            return None
        if self.mock_responses:
            return self.mock_responses.pop(0)
        return None


# ---------------------------------------------------------------------------
# Production transport backed by pyserial
# ---------------------------------------------------------------------------

class PySerialTransport(SerialTransport):
    """
    Production serial transport using pyserial.

    Supports:
      - Windows  : port="COM3", "COM4", …
      - Linux    : port="/dev/ttyUSB0", "/dev/ttyACM0", …

    Configuration is injected at construction time; no hardware constants
    are scattered elsewhere in the codebase.

    All serial.SerialException variants are caught so that the caller
    (PhysicalControllerAdapter) receives a clean bool result rather than
    an unhandled exception propagating into the decision loop.

    WP15 — Ghost-handle protection:
      On Windows, serial.Serial.is_open can remain True for several seconds
      after physical USB removal.  We count consecutive write/read failures;
      once _MAX_IO_FAILURES is reached we force-disconnect so the adapter
      worker sees a real disconnection and enters FAULT/DEGRADED.
    """

    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        connect_timeout: float = 2.0,
        write_timeout: float = 1.0,
        read_timeout: float = 0.1,
    ) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.connect_timeout = connect_timeout
        self.write_timeout = write_timeout
        self.read_timeout = read_timeout
        self._serial = None  # serial.Serial instance, created on connect()
        self._consecutive_io_failures: int = 0

    # ------------------------------------------------------------------
    # SerialTransport interface
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """
        Open the serial port. Returns True on success, False on any error.
        Safe to call when already connected (no-op, returns True).
        Resets the consecutive-failure counter on success.
        """
        if self.is_connected():
            return True
        try:
            import serial  # import deferred so non-serial code paths never fail
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.read_timeout,
                write_timeout=self.write_timeout,
            )
            self._consecutive_io_failures = 0
            logger.info(f"PySerialTransport: connected to {self.port} @ {self.baud_rate}bps.")
            return True
        except Exception as exc:
            logger.error(f"PySerialTransport: connect failed ({self.port}): {exc}")
            self._serial = None
            return False

    def disconnect(self) -> None:
        """Close the port. Safe to call when not connected (no-op)."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception as exc:
                logger.warning(f"PySerialTransport: exception during close: {exc}")
            finally:
                self._serial = None
            self._consecutive_io_failures = 0
            logger.info(f"PySerialTransport: disconnected from {self.port}.")

    def is_connected(self) -> bool:
        """
        Return True when the serial port object exists AND reports is_open.

        NOTE: On Windows this can return True for several seconds after
        physical USB removal (ghost COM handle).  Do NOT rely on this alone
        for liveness decisions — the adapter must use I/O evidence as well.
        """
        return self._serial is not None and self._serial.is_open

    def write_line(self, data: str) -> bool:
        """
        Write data to the port. Returns True on success.
        Ensures the string is newline-terminated before encoding.

        On failure the consecutive-failure counter is incremented.
        Once _MAX_IO_FAILURES is reached the port is force-disconnected
        so the adapter worker detects physical loss even on Windows.
        """
        if not self.is_connected():
            logger.warning("PySerialTransport: write_line called while disconnected.")
            return False
        try:
            payload = data if data.endswith("\n") else data + "\n"
            self._serial.write(payload.encode("utf-8"))
            self._serial.flush()
            self._consecutive_io_failures = 0  # reset on success
            logger.debug(f"[HOST TX] {payload.rstrip()}")
            return True
        except Exception as exc:
            self._consecutive_io_failures += 1
            logger.error(
                f"PySerialTransport: write_line failed (failure #{self._consecutive_io_failures}): {exc}"
            )
            if self._consecutive_io_failures >= _MAX_IO_FAILURES:
                logger.error(
                    f"PySerialTransport: {_MAX_IO_FAILURES} consecutive I/O failures — "
                    "forcing disconnect (USB ghost handle protection)."
                )
                self.disconnect()
            return False

    def read_line(self) -> Optional[str]:
        """
        Read one newline-terminated line from the port.
        Returns None on timeout, disconnection, or decoding error.

        On exception the consecutive-failure counter is incremented.
        Once _MAX_IO_FAILURES is reached the port is force-disconnected.
        """
        if not self.is_connected():
            return None
        try:
            raw = self._serial.readline()
            if not raw:
                return None  # timeout — not an error
            line = raw.decode("utf-8", errors="replace")
            self._consecutive_io_failures = 0  # reset on successful read
            if line.strip():
                logger.debug(f"[HOST RX] {line.rstrip()}")
            return line
        except Exception as exc:
            self._consecutive_io_failures += 1
            logger.error(
                f"PySerialTransport: read_line failed (failure #{self._consecutive_io_failures}): {exc}"
            )
            if self._consecutive_io_failures >= _MAX_IO_FAILURES:
                logger.error(
                    f"PySerialTransport: {_MAX_IO_FAILURES} consecutive I/O failures — "
                    "forcing disconnect (USB ghost handle protection)."
                )
                self.disconnect()
            return None
