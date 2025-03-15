import os
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QWidget, QVBoxLayout, QPushButton, QLabel, QSpinBox, QCheckBox
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsApplication
from .server import QGISMCPServer

class QGISMCPPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock_widget = None
        self.server = None

    def initGui(self):
        # Create action
        self.action = QAction("QGIS MCP", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dock)
        self.iface.addPluginToMenu("&QGIS MCP", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        # Remove the plugin menu and icon
        self.iface.removePluginMenu("&QGIS MCP", self.action)
        self.iface.removeToolBarIcon(self.action)

        # Stop server if running
        if self.server and self.server.running:
            self.server.stop()

    def show_dock(self):
        if self.dock_widget is None:
            # Create the dock widget
            self.dock_widget = QDockWidget("QGIS MCP", self.iface.mainWindow())
            self.dock_widget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

            # Create widget for dock
            dock_contents = QWidget()
            layout = QVBoxLayout(dock_contents)

            # Port selection
            port_label = QLabel("Port:")
            self.port_spin = QSpinBox()
            self.port_spin.setMinimum(1024)
            self.port_spin.setMaximum(65535)
            self.port_spin.setValue(9877)  # Default port (different from Blender)
            layout.addWidget(port_label)
            layout.addWidget(self.port_spin)

            # Start/Stop button
            self.server_button = QPushButton("Start MCP Server")
            self.server_button.clicked.connect(self.toggle_server)
            layout.addWidget(self.server_button)

            # Status label
            self.status_label = QLabel("Server status: Stopped")
            layout.addWidget(self.status_label)

            # Set the widget as the dock content
            self.dock_widget.setWidget(dock_contents)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        else:
            # Show the dock widget if it already exists
            self.dock_widget.setVisible(True)

    def toggle_server(self):
        if self.server and self.server.running:
            # Stop the server
            self.server.stop()
            self.server = None
            self.server_button.setText("Start MCP Server")
            self.status_label.setText("Server status: Stopped")
        else:
            # Start the server
            port = self.port_spin.value()
            self.server = QGISMCPServer(self.iface, port=port)
            self.server.start()
            self.server_button.setText("Stop MCP Server")
            self.status_label.setText(f"Server status: Running on port {port}")