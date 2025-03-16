import socket
import json
import logging
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger("QGISMCP.Connection")

class QGISConnection:
    def __init__(self, host: str = 'localhost', port: int = 9877):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Connect to the QGIS plugin socket server"""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to QGIS at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to QGIS: {str(e)}")
            self.sock = None
            return False

    def disconnect(self) -> None:
        """Disconnect from the QGIS plugin"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from QGIS: {str(e)}")
            finally:
                self.sock = None

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a command to QGIS and return the response"""
        if not self.sock and not self.connect():
            raise ConnectionError("Not connected to QGIS")

        command = {
            "type": command_type,
            "params": params or {}
        }

        try:
            # Send the command
            logger.debug(f"Sending command: {command}")
            self.sock.sendall(json.dumps(command).encode('utf-8'))

            # Receive the response
            chunks = []
            while True:
                chunk = self.sock.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)

                # Try to see if we have a complete JSON
                try:
                    data = b''.join(chunks)
                    response = json.loads(data.decode('utf-8'))

                    if response.get("status") == "error":
                        raise Exception(response.get("message", "Unknown error from QGIS"))

                    return response.get("result", {})
                except json.JSONDecodeError:
                    # Not a complete JSON yet, continue receiving
                    continue

            # If we exit the loop without returning, something went wrong
            raise Exception("Unexpected end of data stream from QGIS")

        except Exception as e:
            logger.error(f"Error communicating with QGIS: {str(e)}")
            self.sock = None
            raise