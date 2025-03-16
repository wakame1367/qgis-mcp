import sys
import logging
import json
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("qgis_mcp.log")
    ]
)
logger = logging.getLogger("QGISMCP")

# Import our connection class
from .connection import QGISConnection

# Global connection instance for reuse
_qgis_connection: Optional[QGISConnection] = None

def get_qgis_connection() -> QGISConnection:
    """Get or create a persistent QGIS connection"""
    global _qgis_connection

    # If we have an existing connection, check if it's still valid
    if _qgis_connection is not None:
        try:
            # Try to ping by getting project info
            _qgis_connection.send_command("get_project_info")
            return _qgis_connection
        except Exception as e:
            # Connection is dead, close it and create a new one
            logger.warning(f"Lost connection to QGIS: {e}")
            try:
                _qgis_connection.disconnect()
            except:
                pass
            _qgis_connection = None

    # Create a new connection if needed
    if _qgis_connection is None:
        _qgis_connection = QGISConnection(host="localhost", port=9877)
        if not _qgis_connection.connect():
            raise ConnectionError("Could not connect to QGIS. Make sure the QGIS MCP plugin is running.")
        logger.info("Created new connection to QGIS")

    return _qgis_connection

# Create the MCP server
mcp = FastMCP(
    "QGISMCP",
    description="QGIS integration through the Model Context Protocol"
)

@mcp.tool()
def get_project_info(ctx: Context) -> str:
    """Get information about the current QGIS project"""
    try:
        qgis = get_qgis_connection()
        result = qgis.send_command("get_project_info")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting project info: {e}")
        return f"Error getting project info: {str(e)}"

@mcp.tool()
def get_layers(ctx: Context) -> str:
    """Get a list of layers in the current QGIS project"""
    try:
        qgis = get_qgis_connection()
        result = qgis.send_command("get_layers")

        # Format the output nicely
        layers = result.get("layers", [])
        output = f"QGIS Project contains {len(layers)} layers:\n\n"

        for i, layer in enumerate(layers, 1):
            output += f"{i}. {layer['name']} ({layer['type']})\n"
            output += f"   ID: {layer['id']}\n"
            output += f"   CRS: {layer['crs']}\n"
            output += f"   Visible: {layer['visible']}\n"

            if layer['type'] == "VectorLayer":
                output += f"   Geometry: {layer.get('geometry_type', 'Unknown')}\n"
                output += f"   Features: {layer.get('feature_count', 0)}\n"
            elif layer['type'] == "RasterLayer":
                output += f"   Size: {layer.get('width', 0)}x{layer.get('height', 0)} pixels\n"
                output += f"   Bands: {layer.get('band_count', 0)}\n"

            output += "\n"

        return output
    except Exception as e:
        logger.error(f"Error getting layers: {e}")
        return f"Error getting layers: {str(e)}"

@mcp.tool()
def add_vector_layer(ctx: Context, path: str, name: str = None, provider: str = "ogr") -> str:
    """
    Add a vector layer to QGIS.

    Parameters:
    - path: Path to the vector data (can be a file, database connection, or URL)
    - name: Layer name to display in QGIS (defaults to filename if not provided)
    - provider: Data provider (usually 'ogr' for vector data)
    """
    try:
        qgis = get_qgis_connection()

        # Use the filename as the layer name if not provided
        if not name:
            name = path.split("/")[-1].split("\\")[-1]
            if "." in name:
                name = name.rsplit(".", 1)[0]

        result = qgis.send_command("add_vector_layer", {
            "path": path,
            "name": name,
            "provider": provider
        })

        return f"Added vector layer '{result['name']}' with {result['feature_count']} features"
    except Exception as e:
        logger.error(f"Error adding vector layer: {e}")
        return f"Error adding vector layer: {str(e)}"

@mcp.tool()
def zoom_to_layer(ctx: Context, layer_name: str) -> str:
    """
    Zoom the map view to a layer's extent.

    Parameters:
    - layer_name: Name of the layer to zoom to
    """
    try:
        qgis = get_qgis_connection()

        # First get the layers to find the ID
        layers = qgis.send_command("get_layers").get("layers", [])
        layer_id = None

        for layer in layers:
            if layer["name"] == layer_name:
                layer_id = layer["id"]
                break

        if not layer_id:
            return f"Layer not found: {layer_name}"

        result = qgis.send_command("zoom_to_layer", {"layer_id": layer_id})
        return f"Zoomed to layer: {result['zoomed_to']}"
    except Exception as e:
        logger.error(f"Error zooming to layer: {e}")
        return f"Error zooming to layer: {str(e)}"

@mcp.tool()
def execute_qgis_code(ctx: Context, code: str) -> str:
    """
    Execute arbitrary Python code in the QGIS Python environment.

    Parameters:
    - code: The Python code to execute
    """
    try:
        qgis = get_qgis_connection()
        result = qgis.send_command("execute_code", {"code": code})
        return "Code executed successfully in QGIS"
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        return f"Error executing code: {str(e)}"

@mcp.tool()
def run_processing_algorithm(ctx: Context, algorithm: str, parameters: Dict[str, Any]) -> str:
    """
    Run a QGIS processing algorithm.

    Parameters:
    - algorithm: The algorithm ID (e.g., 'qgis:buffer')
    - parameters: Dictionary of algorithm parameters
    """
    try:
        qgis = get_qgis_connection()
        result = qgis.send_command("run_processing_algorithm", {
            "algorithm": algorithm,
            "parameters": parameters
        })

        # Format the output nicely
        output = f"Algorithm '{algorithm}' executed successfully.\n\n"
        output += "Results:\n"

        for key, value in result.get("result", {}).items():
            output += f"- {key}: {value}\n"

        return output
    except Exception as e:
        logger.error(f"Error running algorithm: {e}")
        return f"Error running algorithm: {str(e)}"

def main():
    """MCPサーバーのメインエントリーポイント"""
    logger.info("Starting QGIS MCP Server")
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("QGIS MCP Server stopped by user")
    except Exception as e:
        logger.error(f"Error running QGIS MCP Server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()