"""
PySerialTransport tests.
All tests use unittest.mock to patch serial.Serial — NO real COM port or ESP32 required.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from hardware.serial_transport import PySerialTransport, DummySerialTransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transport(port="COM3"):
    return PySerialTransport(
        port=port,
        baud_rate=115200,
        connect_timeout=1.0,
        write_timeout=0.5,
        read_timeout=0.1,
    )


def _connected_transport(mock_serial_cls, port="COM3"):
    """Return a PySerialTransport whose serial.Serial is mocked as open."""
    t = _make_transport(port)
    mock_instance = mock_serial_cls.return_value
    mock_instance.is_open = True
    t.connect()
    return t, mock_instance


# ---------------------------------------------------------------------------
# 1. Successful connect
# ---------------------------------------------------------------------------

def test_pyserial_connect_success():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t = _make_transport()
        result = t.connect()
    assert result is True
    assert t.is_connected()


# ---------------------------------------------------------------------------
# 2. Failed connect (port unavailable)
# ---------------------------------------------------------------------------

def test_pyserial_connect_failure():
    with patch("serial.Serial") as mock_cls:
        import serial as serial_mod
        mock_cls.side_effect = serial_mod.SerialException("Port not found")
        t = _make_transport()
        result = t.connect()
    assert result is False
    assert not t.is_connected()


# ---------------------------------------------------------------------------
# 3. Connect idempotent when already open
# ---------------------------------------------------------------------------

def test_pyserial_connect_idempotent():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        result = t.connect()  # second call
    assert result is True
    assert mock_cls.call_count == 1  # constructor called only once


# ---------------------------------------------------------------------------
# 4. Disconnect
# ---------------------------------------------------------------------------

def test_pyserial_disconnect():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        assert t.is_connected()
        t.disconnect()
    assert t._serial is None


# ---------------------------------------------------------------------------
# 5. is_connected when port is closed
# ---------------------------------------------------------------------------

def test_pyserial_is_connected_false_when_closed():
    t = _make_transport()
    assert not t.is_connected()


# ---------------------------------------------------------------------------
# 6. Successful write
# ---------------------------------------------------------------------------

def test_pyserial_write_success():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        result = t.write_line('{"test": 1}\n')
    assert result is True
    mock_inst.write.assert_called_once()
    mock_inst.flush.assert_called_once()


# ---------------------------------------------------------------------------
# 7. Write auto-appends newline
# ---------------------------------------------------------------------------

def test_pyserial_write_appends_newline():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        t.write_line('{"test": 1}')  # no trailing newline
    written_bytes = mock_inst.write.call_args[0][0]
    assert written_bytes.endswith(b"\n")


# ---------------------------------------------------------------------------
# 8. Failed write (serial exception)
# ---------------------------------------------------------------------------

def test_pyserial_write_failure():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        import serial as serial_mod
        mock_inst.write.side_effect = serial_mod.SerialException("Write error")
        result = t.write_line('{"test": 1}\n')
    assert result is False


# ---------------------------------------------------------------------------
# 9. Write when disconnected
# ---------------------------------------------------------------------------

def test_pyserial_write_when_disconnected():
    t = _make_transport()
    result = t.write_line("data\n")
    assert result is False


# ---------------------------------------------------------------------------
# 10. Successful read
# ---------------------------------------------------------------------------

def test_pyserial_read_success():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        mock_inst.readline.return_value = b'{"version": 1, "type": "ACK"}\n'
        line = t.read_line()
    assert line == '{"version": 1, "type": "ACK"}\n'


# ---------------------------------------------------------------------------
# 11. Read timeout (readline returns empty bytes)
# ---------------------------------------------------------------------------

def test_pyserial_read_timeout():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        mock_inst.readline.return_value = b""
        line = t.read_line()
    assert line is None


# ---------------------------------------------------------------------------
# 12. Read failure (exception from serial layer)
# ---------------------------------------------------------------------------

def test_pyserial_read_failure():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        import serial as serial_mod
        mock_inst.readline.side_effect = serial_mod.SerialException("Read error")
        line = t.read_line()
    assert line is None


# ---------------------------------------------------------------------------
# 13. Read when disconnected
# ---------------------------------------------------------------------------

def test_pyserial_read_when_disconnected():
    t = _make_transport()
    assert t.read_line() is None


# ---------------------------------------------------------------------------
# 14. Disconnect when not connected (no-op, no crash)
# ---------------------------------------------------------------------------

def test_pyserial_disconnect_when_not_connected():
    t = _make_transport()
    t.disconnect()  # must not raise
    assert t._serial is None


# ---------------------------------------------------------------------------
# 15. Close exception is swallowed gracefully
# ---------------------------------------------------------------------------

def test_pyserial_disconnect_close_exception_swallowed():
    with patch("serial.Serial") as mock_cls:
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)
        mock_inst.close.side_effect = OSError("Device gone")
        t.disconnect()  # must not raise
    assert t._serial is None


# ---------------------------------------------------------------------------
# DummySerialTransport — fail_writes flag
# ---------------------------------------------------------------------------

def test_dummy_fail_writes():
    t = DummySerialTransport()
    t.connect()
    t.fail_writes = True
    assert t.write_line("data") is False
    assert t.last_written is None


# ---------------------------------------------------------------------------
# PySerialTransport instantiation with non-default config
# ---------------------------------------------------------------------------

def test_pyserial_custom_config():
    t = PySerialTransport(port="/dev/ttyUSB0", baud_rate=9600, read_timeout=0.5)
    assert t.port == "/dev/ttyUSB0"
    assert t.baud_rate == 9600
    assert t.read_timeout == 0.5


# ---------------------------------------------------------------------------
# WP15 — Ghost-handle / consecutive I/O failure protection
# ---------------------------------------------------------------------------

def test_pyserial_consecutive_write_failures_force_disconnect():
    """
    After _MAX_IO_FAILURES consecutive write exceptions, PySerialTransport
    must call disconnect() proactively so the adapter sees is_connected()==False
    even if the OS handle is still reported as open (Windows ghost handle).
    """
    from hardware.serial_transport import _MAX_IO_FAILURES

    with patch("serial.Serial") as mock_cls:
        import serial as serial_mod
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)

        # Make every write raise a SerialException
        mock_inst.write.side_effect = serial_mod.SerialException("USB removed")

        for _ in range(_MAX_IO_FAILURES):
            result = t.write_line("data\n")
            assert result is False

        # After _MAX_IO_FAILURES failures the port must be force-disconnected
        assert not t.is_connected(), (
            "Expected is_connected()==False after consecutive write failures"
        )
        assert t._serial is None


def test_pyserial_consecutive_read_failures_force_disconnect():
    """
    After _MAX_IO_FAILURES consecutive read exceptions, PySerialTransport
    must force-disconnect.
    """
    from hardware.serial_transport import _MAX_IO_FAILURES

    with patch("serial.Serial") as mock_cls:
        import serial as serial_mod
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)

        mock_inst.readline.side_effect = serial_mod.SerialException("USB removed")

        for _ in range(_MAX_IO_FAILURES):
            result = t.read_line()
            assert result is None

        assert not t.is_connected(), (
            "Expected is_connected()==False after consecutive read failures"
        )
        assert t._serial is None


def test_pyserial_failure_counter_resets_on_success():
    """
    After a successful write, the consecutive-failure counter must reset.
    Failures before + successes after should not accumulate to trigger disconnect.
    """
    from hardware.serial_transport import _MAX_IO_FAILURES

    with patch("serial.Serial") as mock_cls:
        import serial as serial_mod
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)

        # One failure followed by success — must not disconnect
        mock_inst.write.side_effect = serial_mod.SerialException("transient")
        t.write_line("data\n")
        assert t._consecutive_io_failures == 1

        # Success resets the counter
        mock_inst.write.side_effect = None
        t.write_line("data\n")
        assert t._consecutive_io_failures == 0
        assert t.is_connected()


def test_pyserial_connect_resets_failure_counter():
    """
    A successful connect() must reset the consecutive-failure counter to 0.
    """
    with patch("serial.Serial") as mock_cls:
        import serial as serial_mod
        mock_cls.return_value.is_open = True
        t, mock_inst = _connected_transport(mock_cls)

        # Artificially bump the counter
        t._consecutive_io_failures = 99

        # Disconnect and reconnect
        t.disconnect()
        mock_cls.return_value.is_open = True
        t.connect()

        assert t._consecutive_io_failures == 0
