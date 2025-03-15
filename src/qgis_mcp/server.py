import socket
import json
import traceback
import threading
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsApplication
from qgis.utils import iface

class QGISMCPServer:
    def __init__(self, iface, host='localhost', port=9877):
        self.iface = iface
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.client = None
        self.buffer = b''
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()

    def _run_server(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            print(f"QGISMCP server started on {self.host}:{self.port}")

            while self.running:
                try:
                    # Accept connection (with timeout to allow for clean shutdown)
                    self.socket.settimeout(1.0)
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")

                    # Process client communication
                    self._handle_client(client)
                except socket.timeout:
                    # This is expected, just continue the loop to check running status
                    continue
                except Exception as e:
                    print(f"Error in server main loop: {str(e)}")
                    traceback.print_exc()
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
        finally:
            if self.socket:
                self.socket.close()

    def _handle_client(self, client):
        client.settimeout(None)  # No timeout for receiving from client

        try:
            while self.running:
                data = client.recv(8192)
                if not data:
                    # Connection closed by client
                    break

                self.buffer += data

                try:
                    # Try to parse the buffer as JSON
                    command = json.loads(self.buffer.decode('utf-8'))
                    # If successful, clear the buffer and process command
                    self.buffer = b''

                    # Execute the command
                    response = self.execute_command(command)

                    # Send response back to client
                    response_json = json.dumps(response)
                    client.sendall(response_json.encode('utf-8'))
                except json.JSONDecodeError:
                    # Incomplete data, keep in buffer
                    pass
        except Exception as e:
            print(f"Error handling client: {str(e)}")
            traceback.print_exc()
        finally:
            client.close()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.socket:
            self.socket.close()
        print("QGISMCP server stopped")

    def execute_command(self, command):
        """Execute a command and return the response"""
        try:
            cmd_type = command.get("type")
            params = command.get("params", {})

            # Map command types to handler methods
            handlers = {
                "get_project_info": self.get_project_info,
                "get_layers": self.get_layers,
                "add_vector_layer": self.add_vector_layer,
                "add_raster_layer": self.add_raster_layer,
                "zoom_to_layer": self.zoom_to_layer,
                "set_visibility": self.set_visibility,
                "remove_layer": self.remove_layer,
                "execute_code": self.execute_code,
                "run_processing_algorithm": self.run_processing_algorithm,
            }

            handler = handlers.get(cmd_type)
            if handler:
                print(f"Executing handler for {cmd_type}")
                result = handler(**params)
                return {"status": "success", "result": result}
            else:
                return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # Command handlers
    def get_project_info(self):
        """Get information about the current QGIS project"""
        project = QgsProject.instance()

        # Basic project info
        info = {
            "fileName": project.fileName(),
            "title": project.title(),
            "crs": project.crs().authid(),
            "layerCount": len(project.mapLayers()),
        }

        # Get extent if a map canvas is available
        if self.iface and self.iface.mapCanvas():
            extent = self.iface.mapCanvas().extent()
            info["extent"] = {
                "xMin": extent.xMinimum(),
                "yMin": extent.yMinimum(),
                "xMax": extent.xMaximum(),
                "yMax": extent.yMaximum(),
            }

        return info

    def get_layers(self):
        """Get a list of layers in the project"""
        layers = []

        for id, layer in QgsProject.instance().mapLayers().items():
            layer_info = {
                "id": id,
                "name": layer.name(),
                "type": layer.type().name,  # QgsMapLayerType as string
                "crs": layer.crs().authid(),
                "visible": layer.isVisible(),
            }

            # Add type-specific information
            if layer.type().name == "VectorLayer":
                layer_info["geometry_type"] = layer.geometryType().name
                layer_info["feature_count"] = layer.featureCount()

            elif layer.type().name == "RasterLayer":
                layer_info["width"] = layer.width()
                layer_info["height"] = layer.height()
                layer_info["band_count"] = layer.bandCount()

            layers.append(layer_info)

        return {"layers": layers}

    def add_vector_layer(self, path, name, provider="ogr"):
        """Add a vector layer to the project"""
        layer = QgsVectorLayer(path, name, provider)

        if not layer.isValid():
            raise Exception(f"Layer failed to load: {path}")

        QgsProject.instance().addMapLayer(layer)

        return {
            "id": layer.id(),
            "name": layer.name(),
            "feature_count": layer.featureCount(),
        }

    def add_raster_layer(self, path, name, provider="gdal"):
        """Add a raster layer to the project"""
        layer = QgsRasterLayer(path, name, provider)

        if not layer.isValid():
            raise Exception(f"Layer failed to load: {path}")

        QgsProject.instance().addMapLayer(layer)

        return {
            "id": layer.id(),
            "name": layer.name(),
            "width": layer.width(),
            "height": layer.height(),
        }

    def zoom_to_layer(self, layer_id):
        """Zoom the map canvas to a layer's extent"""
        layer = QgsProject.instance().mapLayer(layer_id)

        if not layer:
            raise Exception(f"Layer not found: {layer_id}")

        if self.iface and self.iface.mapCanvas():
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()

        return {"zoomed_to": layer.name()}

    def set_visibility(self, layer_id, visible):
        """Set a layer's visibility"""
        layer = QgsProject.instance().mapLayer(layer_id)

        if not layer:
            raise Exception(f"Layer not found: {layer_id}")

        # Set visibility in legend
        QgsProject.instance().layerTreeRoot().findLayer(layer_id).setItemVisibilityChecked(visible)

        return {"layer": layer.name(), "visible": visible}

    def remove_layer(self, layer_id):
        """Remove a layer from the project"""
        layer = QgsProject.instance().mapLayer(layer_id)

        if not layer:
            raise Exception(f"Layer not found: {layer_id}")

        layer_name = layer.name()
        QgsProject.instance().removeMapLayer(layer_id)

        return {"removed": layer_name}

    def execute_code(self, code):
        """Execute arbitrary Python code in QGIS"""
        # Create a namespace with access to QGIS objects
        namespace = {
            'iface': self.iface,
            'QgsProject': QgsProject,
            'QgsApplication': QgsApplication,
        }

        try:
            # Execute the code
            exec(code, namespace)
            return {"executed": True}
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")

    def run_processing_algorithm(self, algorithm, parameters):
        """Run a processing algorithm"""
        try:
            # Import processing module
            from processing.core.Processing import Processing
            import processing

            # Initialize processing if needed
            if not Processing.isInitialized():
                Processing.initialize()

            # Run the algorithm
            result = processing.run(algorithm, parameters)

            return {
                "algorithm": algorithm,
                "result": result
            }
        except Exception as e:
            raise Exception(f"Error running algorithm: {str(e)}")