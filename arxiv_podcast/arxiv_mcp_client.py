# Modified version of arxiv_mcp_client.py with improvements

import os
import asyncio
import logging
import json
import re
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import uvicorn
from starlette.websockets import WebSocketState

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("arxiv_mcp_client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="ArXiv Research Assistant")

# Configure server path
SERVER_SCRIPT_PATH = os.environ.get("SERVER_SCRIPT_PATH", "arxiv_mcp_server.py")

# Ensure necessary directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

# Set permissions for downloads directory
try:
    os.chmod("downloads", 0o755)
    logger.info("Set permissions for downloads directory")
except Exception as e:
    logger.warning(f"Could not set permissions for downloads directory: {str(e)}")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# MCP Client class
class MCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.available_tools = []
        self.last_paper_id = None
        
    async def connect_to_server(self, server_script_path: str):
        """Connect to the MCP server"""
        logger.info(f"Connecting to MCP server: {server_script_path}")
        
        command = "python"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            await self.session.initialize()

            # List available tools
            response = await self.session.list_tools()
            self.available_tools = response.tools
            tool_names = [tool.name for tool in self.available_tools]
            logger.info(f"Connected to server with tools: {tool_names}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to server: {str(e)}")
            return False
    
    async def process_message(self, message: str) -> str:
        """Process a message using the MCP server"""
        if not self.session:
            return json.dumps({
                "success": False,
                "message": "Error: Not connected to server"
            }, indent=2)
        
        try:
            # Check if this is a direct download request
            download_match = re.search(r'download\s+(?:paper|article)?\s*(?:with)?\s*(?:id|arxiv id|number)?\s*:?\s*(\d+\.\d+v?\d*)', message.lower())
            
            if download_match:
                # Direct download request
                paper_id = download_match.group(1)
                logger.info(f"Direct download request detected in client for ID: {paper_id}")
                self.last_paper_id = paper_id
                result = await self.session.call_tool("download_paper", {"paper_id": paper_id})
                return result.content
            
            # Check for "download it" or similar phrases that refer to the last paper
            if re.search(r'download\s+(?:it|this|that|the\s+paper)', message.lower()) and self.last_paper_id:
                logger.info(f"Download request for last referenced paper: {self.last_paper_id}")
                result = await self.session.call_tool("download_paper", {"paper_id": self.last_paper_id})
                return result.content
            
            # Use natural language processing tool to handle the message
            result = await self.session.call_tool("process_natural_language_query", {"query": message})
            
            # Try to extract paper ID if this is a search result (for potential later download)
            try:
                response_data = json.loads(result.content)
                if isinstance(response_data, dict) and 'papers' in response_data and len(response_data['papers']) > 0:
                    # Store the first paper ID for potential later download
                    self.last_paper_id = response_data['papers'][0]['id']
                    logger.info(f"Saved first paper ID from search results: {self.last_paper_id}")
            except:
                pass
                
            return result.content
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return json.dumps({
                "success": False,
                "message": f"Error processing your message: {str(e)}"
            }, indent=2)
    
    async def get_paper_details(self, paper_id: str) -> str:
        """Get details for a specific paper"""
        if not self.session:
            return json.dumps({
                "success": False,
                "message": "Error: Not connected to server"
            }, indent=2)
        
        try:
            # Save this paper ID for potential download
            self.last_paper_id = paper_id
            logger.info(f"Getting details and saving paper ID: {paper_id}")
            
            result = await self.session.call_tool("get_paper_details", {"paper_id": paper_id})
            return result.content
        except Exception as e:
            logger.error(f"Error getting paper details: {str(e)}")
            return json.dumps({
                "success": False,
                "message": f"Error getting paper details: {str(e)}"
            }, indent=2)
    
    async def download_paper(self, paper_id: str, download_dir: str = "./downloads") -> str:
        """Download a paper by ID
        
        Args:
            paper_id: The ID of the paper to download
            download_dir: Directory to save the downloaded paper
        """
        if not self.session:
            return json.dumps({
                "success": False,
                "message": "Error: Not connected to server"
            }, indent=2)
        
        try:
            # Save this paper ID for potential download
            self.last_paper_id = paper_id
            logger.info(f"Downloading paper ID: {paper_id}")
            
            result = await self.session.call_tool("download_paper", {
                "paper_id": paper_id, 
                "download_dir": download_dir
            })
            return result.content
        except Exception as e:
            logger.error(f"Error downloading paper: {str(e)}")
            return json.dumps({
                "success": False,
                "message": f"Error downloading paper: {str(e)}"
            }, indent=2)
    
    async def cleanup(self):
        """Clean up resources"""
        if self.exit_stack:
            await self.exit_stack.aclose()

# Initialize MCP client
mcp_client = MCPClient()

# API routes
@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Initialize server connection
    if not mcp_client.session:
        connected = await mcp_client.connect_to_server(SERVER_SCRIPT_PATH)
        if not connected:
            await manager.send_message(json.dumps({
                "type": "error",
                "message": "Failed to connect to the arXiv MCP server"
            }), websocket)
            manager.disconnect(websocket)
            return
    
    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            
            message_type = data_json.get("type", "message")
            
            if message_type == "message":
                # Process regular message
                user_message = data_json.get("message", "")
                await manager.send_message(json.dumps({
                    "type": "status",
                    "message": "Processing your request..."
                }), websocket)
                
                # Check if this is a download request that we can handle directly
                download_match = re.search(r'download.*?(\d+\.\d+v?\d*)', user_message.lower())
                if download_match:
                    # Direct download request
                    paper_id = download_match.group(1)
                    logger.info(f"Direct download request detected for ID: {paper_id}")
                    
                    try:
                        response = await mcp_client.download_paper(paper_id)
                        
                        # Try to parse as JSON
                        try:
                            response_data = json.loads(response)
                            if isinstance(response_data, dict) and "success" in response_data:
                                if response_data["success"]:
                                    await manager.send_message(json.dumps({
                                        "type": "download_result",
                                        "message": response_data["message"],
                                        "filepath": response_data.get("filepath", ""),
                                        "title": response_data.get("title", "")
                                    }), websocket)
                                else:
                                    await manager.send_message(json.dumps({
                                        "type": "error",
                                        "message": response_data["message"]
                                    }), websocket)
                            else:
                                # Not in the expected format, just pass it through
                                await manager.send_message(json.dumps({
                                    "type": "download_result",
                                    "message": response
                                }), websocket)
                        except json.JSONDecodeError:
                            # Not JSON, treat as string
                            await manager.send_message(json.dumps({
                                "type": "download_result",
                                "message": response
                            }), websocket)
                    except Exception as e:
                        logger.error(f"Error downloading paper: {str(e)}")
                        await manager.send_message(json.dumps({
                            "type": "error",
                            "message": f"Error downloading paper: {str(e)}"
                        }), websocket)
                else:
                    # Regular query processing
                    try:
                        # Send the query to the natural language processor
                        response = await mcp_client.process_message(user_message)
                        
                        # Try to parse it as JSON
                        try:
                            # Check if it's valid JSON
                            json_data = json.loads(response)
                            
                            # If it is JSON, format it nicely before sending
                            if isinstance(json_data, dict) and 'papers' in json_data:
                                # This is a paper search result
                                await manager.send_message(json.dumps({
                                    "type": "message",
                                    "message": json_data.get("message", "Search results:"),
                                    "is_search_result": True,
                                    "papers": json_data.get("papers", []),
                                    "total_papers": json_data.get("total_found", len(json_data.get("papers", [])))
                                }), websocket)
                            else:
                                # Other type of JSON response
                                await manager.send_message(json.dumps({
                                    "type": "message",
                                    "message": json.dumps(json_data, indent=2)
                                }), websocket)
                        except json.JSONDecodeError:
                            # Not JSON, treat as a regular message
                            await manager.send_message(json.dumps({
                                "type": "message",
                                "message": response
                            }), websocket)
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        await manager.send_message(json.dumps({
                            "type": "error",
                            "message": f"Error processing message: {str(e)}"
                        }), websocket)
            
            elif message_type == "paper_details":
                # Get paper details
                paper_id = data_json.get("paper_id", "")
                
                try:
                    response = await mcp_client.get_paper_details(paper_id)
                    
                    # Try to parse as JSON
                    try:
                        response_data = json.loads(response)
                        if isinstance(response_data, dict) and "success" in response_data:
                            if response_data["success"] and response_data.get("paper"):
                                paper = response_data["paper"]
                                # Format the details in a readable way
                                formatted_details = f"""
# Paper Details

**ID**: {paper['id']}
**Title**: {paper['title']}
**Author(s)**: {paper['all_authors']}
**Date**: {paper['date']}
**Categories**: {paper['categories']}
**PDF URL**: {paper['pdf_url']}

## Abstract
{paper['abstract']}
                                """
                                await manager.send_message(json.dumps({
                                    "type": "paper_details",
                                    "message": formatted_details
                                }), websocket)
                            else:
                                await manager.send_message(json.dumps({
                                    "type": "error",
                                    "message": response_data.get("message", "Error retrieving paper details")
                                }), websocket)
                        else:
                            # Not in the expected format, just pass it through
                            await manager.send_message(json.dumps({
                                "type": "paper_details",
                                "message": response
                            }), websocket)
                    except json.JSONDecodeError:
                        # Not JSON, treat as string
                        await manager.send_message(json.dumps({
                            "type": "paper_details",
                            "message": response
                        }), websocket)
                except Exception as e:
                    logger.error(f"Error getting paper details: {str(e)}")
                    await manager.send_message(json.dumps({
                        "type": "error",
                        "message": f"Error getting paper details: {str(e)}"
                    }), websocket)
            
            elif message_type == "download_paper":
                # Download paper
                paper_id = data_json.get("paper_id", "")
                download_dir = data_json.get("download_dir", "./downloads")
                
                try:
                    response = await mcp_client.download_paper(paper_id, download_dir)
                    
                    # Try to parse as JSON
                    try:
                        response_data = json.loads(response)
                        if isinstance(response_data, dict) and "success" in response_data:
                            if response_data["success"]:
                                await manager.send_message(json.dumps({
                                    "type": "download_result",
                                    "message": response_data["message"],
                                    "filepath": response_data.get("filepath", ""),
                                    "title": response_data.get("title", "")
                                }), websocket)
                            else:
                                await manager.send_message(json.dumps({
                                    "type": "error",
                                    "message": response_data["message"]
                                }), websocket)
                        else:
                            # Not in the expected format, just pass it through
                            await manager.send_message(json.dumps({
                                "type": "download_result",
                                "message": response
                            }), websocket)
                    except json.JSONDecodeError:
                        # Not JSON, treat as string
                        await manager.send_message(json.dumps({
                            "type": "download_result",
                            "message": response
                        }), websocket)
                except Exception as e:
                    logger.error(f"Error downloading paper: {str(e)}")
                    await manager.send_message(json.dumps({
                        "type": "error",
                        "message": f"Error downloading paper: {str(e)}"
                    }), websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
        try:
            await manager.send_message(json.dumps({
                "type": "error",
                "message": f"An error occurred: {str(e)}"
            }), websocket)
        except:
            pass
        manager.disconnect(websocket)

# Define lifespan events for FastAPI
@app.on_event("startup")
async def startup_event():
    logger.info("Starting arXiv Research Assistant client")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down arXiv Research Assistant client")
    await mcp_client.cleanup()

# Main entry point
if __name__ == "__main__":
    # Start the web server
    uvicorn.run(app, host="0.0.0.0", port=8000)