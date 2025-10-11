#!/usr/bin/env python3
"""
Configuration and Health Monitoring Router
Handles gateway configuration and server health monitoring endpoints
"""
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from tools_gateway import config_manager
from tools_gateway import discovery_service

logger = logging.getLogger(__name__)

# Create router without prefix since routes are at root level
router = APIRouter(tags=["config", "health"])


@router.get("/config")
async def get_config():
    """Get current gateway configuration"""
    config = config_manager.get_all_config()
    # Convert datetime to string for JSON serialization
    return JSONResponse(content=json.loads(json.dumps(config, default=str)))


@router.post("/config/health")
async def update_health_config(request_data: Dict[str, Any]):
    """Update connection health monitoring configuration"""
    try:
        updated_config = config_manager.update_connection_health_config(**request_data)

        # Restart health monitoring with new config
        await discovery_service.stop_health_monitoring()
        await discovery_service.start_health_monitoring()

        return JSONResponse(content={
            "success": True,
            "config": updated_config.model_dump()
        })
    except Exception as e:
        logger.error(f"Error updating health config: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@router.post("/config/origin/add")
async def add_allowed_origin(request_data: Dict[str, Any]):
    """Add an allowed origin"""
    try:
        origin = request_data.get("origin")
        if not origin:
            return JSONResponse(content={
                "error": "origin parameter required"
            }, status_code=400)

        success = config_manager.add_allowed_origin(origin)
        return JSONResponse(content={
            "success": success,
            "message": f"Origin '{origin}' {'added' if success else 'already exists'}"
        })
    except Exception as e:
        logger.error(f"Error adding origin: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@router.post("/config/origin/remove")
async def remove_allowed_origin(request_data: Dict[str, Any]):
    """Remove an allowed origin"""
    try:
        origin = request_data.get("origin")
        if not origin:
            return JSONResponse(content={
                "error": "origin parameter required"
            }, status_code=400)

        success = config_manager.remove_allowed_origin(origin)
        return JSONResponse(content={
            "success": success,
            "message": f"Origin '{origin}' {'removed' if success else 'not found'}"
        })
    except Exception as e:
        logger.error(f"Error removing origin: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@router.post("/config/origin")
async def update_origin_config(request_data: Dict[str, Any]):
    """Update origin configuration (allow_ngrok, allow_https)"""
    try:
        updated_config = config_manager.update_origin_config(**request_data)
        return JSONResponse(content={
            "success": True,
            "config": updated_config.model_dump()
        })
    except Exception as e:
        logger.error(f"Error updating origin config: {e}")
        return JSONResponse(content={
            "error": str(e)
        }, status_code=400)


@router.get("/health/servers")
async def get_servers_health():
    """Get health status of all connected servers"""
    return JSONResponse(content=discovery_service.get_server_health_status())


@router.get("/health/servers/{server_url:path}")
async def get_server_health(server_url: str):
    """Get health status of a specific server"""
    return JSONResponse(content=discovery_service.get_server_health_status(server_url))
