def classFactory(iface):
    from .qgis_mcp_plugin import QGISMCPPlugin
    return QGISMCPPlugin(iface)