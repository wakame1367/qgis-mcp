def classFactory(iface):
    from .qgis_mcp import QGISMCPPlugin
    return QGISMCPPlugin(iface)