"""Import/Export System v2.9.4 - Backup and restore all CrackedCode data.

Export everything to a ZIP archive:
  - Conversations (SQLite database)
  - Long-term memories (JSON)
  - Metrics (JSON)
  - Custom agents (JSON/YAML)
  - Schedules (JSON/YAML)
  - Configuration (JSON)
  - Plugins (Python files)

Usage:
    from src.import_export import ImportExportManager
    mgr = ImportExportManager()
    mgr.export_all("backup.zip")
    mgr.import_all("backup.zip")
"""

import json
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("ImportExport")


@dataclass
class ExportManifest:
    """Manifest describing an export archive."""
    version: str = "2.9.4"
    exported_at: float = 0.0
    items: List[str] = None
    
    def __post_init__(self):
        if self.items is None:
            self.items = []


class ImportExportManager:
    """Manage import and export of all CrackedCode data."""
    
    EXPORT_ITEMS = [
        "config",
        "conversations",
        "memories",
        "metrics",
        "agents",
        "schedules",
        "plugins",
    ]
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.data_dir = self.project_root / ".crackedcode"
    
    def export_all(self, output_path: str, items: Optional[List[str]] = None) -> Dict[str, Any]:
        """Export all data to a ZIP archive.
        
        Args:
            output_path: Path to output ZIP file
            items: List of items to export (None = all)
        
        Returns:
            Export summary dict
        """
        items = items or self.EXPORT_ITEMS
        output = Path(output_path)
        
        manifest = ExportManifest(
            version="2.9.4",
            exported_at=time.time(),
            items=[],
        )
        
        results = {}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Export config
            if "config" in items:
                try:
                    config_src = self.project_root / "config.json"
                    if config_src.exists():
                        shutil.copy2(config_src, tmpdir / "config.json")
                        manifest.items.append("config")
                        results["config"] = True
                except Exception as e:
                    logger.warning(f"Export config failed: {e}")
                    results["config"] = False
            
            # Export conversations
            if "conversations" in items:
                try:
                    conv_src = self.data_dir / "conversations.db"
                    if conv_src.exists():
                        shutil.copy2(conv_src, tmpdir / "conversations.db")
                        manifest.items.append("conversations")
                        results["conversations"] = True
                except Exception as e:
                    logger.warning(f"Export conversations failed: {e}")
                    results["conversations"] = False
            
            # Export memories
            if "memories" in items:
                try:
                    mem_src = self.data_dir / "memory" / "memories.json"
                    if mem_src.exists():
                        mem_dir = tmpdir / "memory"
                        mem_dir.mkdir(exist_ok=True)
                        shutil.copy2(mem_src, mem_dir / "memories.json")
                        manifest.items.append("memories")
                        results["memories"] = True
                except Exception as e:
                    logger.warning(f"Export memories failed: {e}")
                    results["memories"] = False
            
            # Export metrics
            if "metrics" in items:
                try:
                    met_src = self.data_dir / "metrics" / "metrics.json"
                    if met_src.exists():
                        met_dir = tmpdir / "metrics"
                        met_dir.mkdir(exist_ok=True)
                        shutil.copy2(met_src, met_dir / "metrics.json")
                        manifest.items.append("metrics")
                        results["metrics"] = True
                except Exception as e:
                    logger.warning(f"Export metrics failed: {e}")
                    results["metrics"] = False
            
            # Export agents
            if "agents" in items:
                try:
                    agents_dir = self.project_root / "agents"
                    if agents_dir.exists():
                        shutil.copytree(agents_dir, tmpdir / "agents")
                        manifest.items.append("agents")
                        results["agents"] = True
                except Exception as e:
                    logger.warning(f"Export agents failed: {e}")
                    results["agents"] = False
            
            # Export schedules
            if "schedules" in items:
                try:
                    sched_dir = self.project_root / "schedules"
                    if sched_dir.exists():
                        shutil.copytree(sched_dir, tmpdir / "schedules")
                        manifest.items.append("schedules")
                        results["schedules"] = True
                except Exception as e:
                    logger.warning(f"Export schedules failed: {e}")
                    results["schedules"] = False
            
            # Export plugins
            if "plugins" in items:
                try:
                    plugin_dir = self.project_root / "plugins"
                    if plugin_dir.exists():
                        shutil.copytree(plugin_dir, tmpdir / "plugins")
                        manifest.items.append("plugins")
                        results["plugins"] = True
                except Exception as e:
                    logger.warning(f"Export plugins failed: {e}")
                    results["plugins"] = False
            
            # Write manifest
            with open(tmpdir / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest.__dict__, f, indent=2)
            
            # Create ZIP
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in tmpdir.iterdir():
                    if item.is_file():
                        zf.write(item, item.name)
                    elif item.is_dir():
                        for file in item.rglob("*"):
                            if file.is_file():
                                zf.write(file, file.relative_to(tmpdir))
            
            logger.info(f"Exported {len(manifest.items)} items to {output}")
        
        return {
            "success": True,
            "path": str(output),
            "items_exported": manifest.items,
            "results": results,
        }
    
    def import_all(self, input_path: str, items: Optional[List[str]] = None,
                   overwrite: bool = False) -> Dict[str, Any]:
        """Import data from a ZIP archive.
        
        Args:
            input_path: Path to input ZIP file
            items: List of items to import (None = all in archive)
            overwrite: Whether to overwrite existing data
        
        Returns:
            Import summary dict
        """
        input_file = Path(input_path)
        if not input_file.exists():
            return {"success": False, "error": f"File not found: {input_path}"}
        
        results = {}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Extract ZIP
            with zipfile.ZipFile(input_file, "r") as zf:
                zf.extractall(tmpdir)
            
            # Read manifest
            manifest_path = tmpdir / "manifest.json"
            if not manifest_path.exists():
                return {"success": False, "error": "Invalid backup: manifest.json not found"}
            
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            available_items = manifest.get("items", [])
            items_to_import = items or available_items
            
            # Import config
            if "config" in items_to_import and "config" in available_items:
                try:
                    config_src = tmpdir / "config.json"
                    if config_src.exists():
                        config_dest = self.project_root / "config.json"
                        if not config_dest.exists() or overwrite:
                            shutil.copy2(config_src, config_dest)
                            results["config"] = True
                        else:
                            results["config"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import config failed: {e}")
                    results["config"] = False
            
            # Import conversations
            if "conversations" in items_to_import and "conversations" in available_items:
                try:
                    conv_src = tmpdir / "conversations.db"
                    if conv_src.exists():
                        conv_dir = self.data_dir
                        conv_dir.mkdir(parents=True, exist_ok=True)
                        conv_dest = conv_dir / "conversations.db"
                        if not conv_dest.exists() or overwrite:
                            shutil.copy2(conv_src, conv_dest)
                            results["conversations"] = True
                        else:
                            results["conversations"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import conversations failed: {e}")
                    results["conversations"] = False
            
            # Import memories
            if "memories" in items_to_import and "memories" in available_items:
                try:
                    mem_src = tmpdir / "memory" / "memories.json"
                    if mem_src.exists():
                        mem_dir = self.data_dir / "memory"
                        mem_dir.mkdir(parents=True, exist_ok=True)
                        mem_dest = mem_dir / "memories.json"
                        if not mem_dest.exists() or overwrite:
                            shutil.copy2(mem_src, mem_dest)
                            results["memories"] = True
                        else:
                            results["memories"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import memories failed: {e}")
                    results["memories"] = False
            
            # Import metrics
            if "metrics" in items_to_import and "metrics" in available_items:
                try:
                    met_src = tmpdir / "metrics" / "metrics.json"
                    if met_src.exists():
                        met_dir = self.data_dir / "metrics"
                        met_dir.mkdir(parents=True, exist_ok=True)
                        met_dest = met_dir / "metrics.json"
                        if not met_dest.exists() or overwrite:
                            shutil.copy2(met_src, met_dest)
                            results["metrics"] = True
                        else:
                            results["metrics"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import metrics failed: {e}")
                    results["metrics"] = False
            
            # Import agents
            if "agents" in items_to_import and "agents" in available_items:
                try:
                    agents_src = tmpdir / "agents"
                    if agents_src.exists():
                        agents_dest = self.project_root / "agents"
                        if not agents_dest.exists() or overwrite:
                            if agents_dest.exists():
                                shutil.rmtree(agents_dest)
                            shutil.copytree(agents_src, agents_dest)
                            results["agents"] = True
                        else:
                            results["agents"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import agents failed: {e}")
                    results["agents"] = False
            
            # Import schedules
            if "schedules" in items_to_import and "schedules" in available_items:
                try:
                    sched_src = tmpdir / "schedules"
                    if sched_src.exists():
                        sched_dest = self.project_root / "schedules"
                        if not sched_dest.exists() or overwrite:
                            if sched_dest.exists():
                                shutil.rmtree(sched_dest)
                            shutil.copytree(sched_src, sched_dest)
                            results["schedules"] = True
                        else:
                            results["schedules"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import schedules failed: {e}")
                    results["schedules"] = False
            
            # Import plugins
            if "plugins" in items_to_import and "plugins" in available_items:
                try:
                    plugin_src = tmpdir / "plugins"
                    if plugin_src.exists():
                        plugin_dest = self.project_root / "plugins"
                        if not plugin_dest.exists() or overwrite:
                            if plugin_dest.exists():
                                shutil.rmtree(plugin_dest)
                            shutil.copytree(plugin_src, plugin_dest)
                            results["plugins"] = True
                        else:
                            results["plugins"] = "skipped (exists)"
                except Exception as e:
                    logger.warning(f"Import plugins failed: {e}")
                    results["plugins"] = False
            
            logger.info(f"Imported {len([v for v in results.values() if v is True])} items from {input_file}")
        
        return {
            "success": True,
            "path": str(input_file),
            "manifest_version": manifest.get("version", "unknown"),
            "results": results,
        }
    
    def get_exportable_items(self) -> List[str]:
        """Get list of items that can be exported."""
        available = []
        
        if (self.project_root / "config.json").exists():
            available.append("config")
        if (self.data_dir / "conversations.db").exists():
            available.append("conversations")
        if (self.data_dir / "memory" / "memories.json").exists():
            available.append("memories")
        if (self.data_dir / "metrics" / "metrics.json").exists():
            available.append("metrics")
        if (self.project_root / "agents").exists():
            available.append("agents")
        if (self.project_root / "schedules").exists():
            available.append("schedules")
        if (self.project_root / "plugins").exists():
            available.append("plugins")
        
        return available


def create_import_export_manager(project_root: str = ".") -> ImportExportManager:
    """Create an ImportExportManager instance."""
    return ImportExportManager(project_root=project_root)
