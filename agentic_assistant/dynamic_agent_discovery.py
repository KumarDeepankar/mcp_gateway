# dynamic_agent_discovery.py
"""
Dynamic Agent and Tool Discovery Service
Provides centralized, plugin-friendly discovery of agents and tools from agent_interface
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
import aiohttp
import logging

from settings import AGENT_INTERFACE_BASE_URL

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool categories for classification"""
    VISUALIZATION = "visualization"
    DATA_ANALYSIS = "data_analysis"
    RESEARCH = "research"
    COMMUNICATION = "communication" 
    GENERAL = "general"


@dataclass
class DynamicAgentInfo:
    """Information about a dynamically discovered agent"""
    agent_id: str
    name: str
    description: str
    skills: List[Dict[str, Any]]
    service_endpoint: str
    metadata: Dict[str, Any]


@dataclass
class DynamicSkillInfo:
    """Information about a dynamically discovered skill"""
    skill_id: str
    name: str
    description: str
    agent_id: str
    agent_name: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    category: ToolCategory
    tags: List[str]
    is_chart_tool: bool
    metadata: Dict[str, Any]


class DynamicAgentDiscoveryService:
    """Service for dynamically discovering agents and their skills"""
    
    def __init__(self):
        self._agents_cache: Dict[str, DynamicAgentInfo] = {}
        self._skills_cache: Dict[str, DynamicSkillInfo] = {}
        self._cache_timeout = 300  # 5 minutes
        self._last_refresh = 0
        self._refresh_lock = asyncio.Lock()
    
    async def refresh_cache(self, http_session: aiohttp.ClientSession, force: bool = False) -> bool:
        """Refresh the agents and skills cache"""
        import time
        current_time = time.time()
        
        if not force and current_time - self._last_refresh < self._cache_timeout:
            return True
        
        async with self._refresh_lock:
            try:
                # Double-check after acquiring lock
                if not force and current_time - self._last_refresh < self._cache_timeout:
                    return True
                
                logger.info("Refreshing dynamic agent discovery cache...")
                
                # Discover agents using JSON-RPC agent.list endpoint
                jsonrpc_request = {
                    "jsonrpc": "2.0",
                    "method": "agent.list",
                    "params": {"format": "cards"},
                    "id": f"discovery_{uuid.uuid4().hex[:8]}"
                }
                
                async with http_session.post(
                    f"{AGENT_INTERFACE_BASE_URL}/rpc",
                    json=jsonrpc_request,
                    headers={"Content-Type": "application/json"},
                    timeout=15
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to refresh agent cache: HTTP {response.status}")
                        return False
                    
                    response_data = await response.json()
                    if "error" in response_data:
                        logger.error(f"JSON-RPC error refreshing cache: {response_data['error']}")
                        return False
                    
                    agent_cards = response_data.get("result", {}).get("agent_cards", {})
                    
                    # Clear caches
                    self._agents_cache.clear()
                    self._skills_cache.clear()
                    
                    # Process agent cards
                    for agent_id, agent_card in agent_cards.items():
                        # Create agent info
                        agent_info = DynamicAgentInfo(
                            agent_id=agent_id,
                            name=agent_card.get("name", agent_id),
                            description=agent_card.get("description", ""),
                            skills=agent_card.get("skills", []),
                            service_endpoint=agent_card.get("service_endpoint", ""),
                            metadata=agent_card.get("metadata", {})
                        )
                        self._agents_cache[agent_id] = agent_info
                        
                        # Process skills
                        for skill in agent_card.get("skills", []):
                            skill_info = self._create_skill_info(skill, agent_info)
                            self._skills_cache[skill_info.skill_id] = skill_info
                    
                    self._last_refresh = current_time
                    logger.info(f"Refreshed cache: {len(self._agents_cache)} agents, {len(self._skills_cache)} skills")
                    return True
                    
            except Exception as e:
                logger.error(f"Exception refreshing agent cache: {e}")
                return False
    
    def _create_skill_info(self, skill: Dict[str, Any], agent_info: DynamicAgentInfo) -> DynamicSkillInfo:
        """Create a DynamicSkillInfo from skill data"""
        skill_id = skill.get("skill_id", "")
        skill_name = skill.get("name", skill_id)
        tags = skill.get("metadata", {}).get("tags", [])
        
        # Determine category and chart tool status
        category = self._categorize_skill(skill_name, skill.get("description", ""), tags)
        is_chart_tool = category == ToolCategory.VISUALIZATION or "visualization" in tags
        
        return DynamicSkillInfo(
            skill_id=skill_id,
            name=skill_name,
            description=skill.get("description", ""),
            agent_id=agent_info.agent_id,
            agent_name=agent_info.name,
            input_schema=skill.get("input_schema", {}),
            output_schema=skill.get("output_schema", {}),
            category=category,
            tags=tags,
            is_chart_tool=is_chart_tool,
            metadata=skill.get("metadata", {})
        )
    
    def _categorize_skill(self, name: str, description: str, tags: List[str]) -> ToolCategory:
        """Categorize a skill based on its name, description, and tags"""
        name_lower = name.lower()
        desc_lower = description.lower()
        
        # Check tags first
        if "visualization" in tags or "data_analysis" in tags:
            return ToolCategory.VISUALIZATION
        if "research" in tags:
            return ToolCategory.RESEARCH
        if "communication" in tags:
            return ToolCategory.COMMUNICATION
        
        # Check name and description
        viz_keywords = ["chart", "plot", "graph", "visual", "analyze", "data"]
        research_keywords = ["search", "research", "find", "query", "investigate"]
        comm_keywords = ["joke", "hello", "greet", "chat", "message"]
        
        if any(keyword in name_lower or keyword in desc_lower for keyword in viz_keywords):
            return ToolCategory.VISUALIZATION
        elif any(keyword in name_lower or keyword in desc_lower for keyword in research_keywords):
            return ToolCategory.RESEARCH
        elif any(keyword in name_lower or keyword in desc_lower for keyword in comm_keywords):
            return ToolCategory.COMMUNICATION
        
        return ToolCategory.GENERAL
    
    async def get_all_skills(self, http_session: aiohttp.ClientSession) -> List[DynamicSkillInfo]:
        """Get all available skills"""
        await self.refresh_cache(http_session)
        return list(self._skills_cache.values())
    
    async def get_skills_by_category(self, category: ToolCategory, http_session: aiohttp.ClientSession) -> List[DynamicSkillInfo]:
        """Get skills filtered by category"""
        await self.refresh_cache(http_session)
        return [skill for skill in self._skills_cache.values() if skill.category == category]
    
    async def get_chart_tools(self, http_session: aiohttp.ClientSession) -> List[DynamicSkillInfo]:
        """Get all chart/visualization tools"""
        await self.refresh_cache(http_session)
        return [skill for skill in self._skills_cache.values() if skill.is_chart_tool]
    
    async def find_skill_by_name(self, name: str, http_session: aiohttp.ClientSession) -> Optional[DynamicSkillInfo]:
        """Find a skill by name (fuzzy matching)"""
        await self.refresh_cache(http_session)
        
        # Exact match first
        for skill in self._skills_cache.values():
            if skill.name.lower() == name.lower():
                return skill
        
        # Partial match
        for skill in self._skills_cache.values():
            if name.lower() in skill.name.lower() or skill.name.lower() in name.lower():
                return skill
        
        return None
    
    async def get_skill_by_id(self, skill_id: str, http_session: aiohttp.ClientSession) -> Optional[DynamicSkillInfo]:
        """Get a skill by its ID"""
        await self.refresh_cache(http_session)
        return self._skills_cache.get(skill_id)
    
    async def get_agent_info(self, agent_id: str, http_session: aiohttp.ClientSession) -> Optional[DynamicAgentInfo]:
        """Get agent information by ID"""
        await self.refresh_cache(http_session)
        return self._agents_cache.get(agent_id)
    
    async def get_skills_for_query(self, query: str, http_session: aiohttp.ClientSession) -> List[DynamicSkillInfo]:
        """Get relevant skills for a user query using keyword matching"""
        await self.refresh_cache(http_session)
        query_lower = query.lower()
        
        relevant_skills = []
        
        # Look for visualization/chart keywords
        viz_keywords = ["chart", "plot", "graph", "visual", "show", "display", "analyze", "data"]
        if any(keyword in query_lower for keyword in viz_keywords):
            relevant_skills.extend(await self.get_skills_by_category(ToolCategory.VISUALIZATION, http_session))
        
        # Look for research keywords  
        research_keywords = ["search", "find", "research", "investigate", "look up"]
        if any(keyword in query_lower for keyword in research_keywords):
            relevant_skills.extend(await self.get_skills_by_category(ToolCategory.RESEARCH, http_session))
        
        # Look for communication keywords
        comm_keywords = ["joke", "hello", "greet", "chat"]
        if any(keyword in query_lower for keyword in comm_keywords):
            relevant_skills.extend(await self.get_skills_by_category(ToolCategory.COMMUNICATION, http_session))
        
        # Remove duplicates
        seen_ids = set()
        unique_skills = []
        for skill in relevant_skills:
            if skill.skill_id not in seen_ids:
                seen_ids.add(skill.skill_id)
                unique_skills.append(skill)
        
        return unique_skills
    
    def get_cached_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "agents": len(self._agents_cache),
            "skills": len(self._skills_cache),
            "chart_tools": len([s for s in self._skills_cache.values() if s.is_chart_tool])
        }


# Global singleton instance
_discovery_service: Optional[DynamicAgentDiscoveryService] = None

def get_discovery_service() -> DynamicAgentDiscoveryService:
    """Get the global discovery service instance"""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = DynamicAgentDiscoveryService()
    return _discovery_service