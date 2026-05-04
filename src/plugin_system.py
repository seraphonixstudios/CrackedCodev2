"""Plugin System - Extensible hooks for custom agent behavior.

Provides a lightweight plugin architecture with:
- @plugin decorator for auto-registration
- Hook-based event system (engine, orchestrator, GUI, lifecycle)
- Hot-reload via file watcher integration
- Sandboxed execution with error isolation

Architecture:
    @plugin decorator → PluginRegistry → HookManager → (Engine/Orchestrator/GUI)
"""

import os
import sys
import time
import inspect
import importlib.util
import traceback
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps

from src.logger_config import get_logger

logger = get_logger("PluginSystem")


class HookPoint(Enum):
    """Named hook points across the system."""
    ENGINE_PRE_PROCESS = "engine.pre_process"
    ENGINE_POST_PROCESS = "engine.post_process"
    ENGINE_INTENT_PARSED = "engine.intent_parsed"
    ORCHESTRATOR_TASK_CREATED = "orchestrator.task_created"
    ORCHESTRATOR_TASK_COMPLETED = "orchestrator.task_completed"
    ORCHESTRATOR_TASK_FAILED = "orchestrator.task_failed"
    GUI_MENU_READY = "gui.menu_ready"
    GUI_COMMAND_PALETTE = "gui.command_palette"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    TOOL_PRE_EXECUTE = "tool.pre_execute"
    TOOL_POST_EXECUTE = "tool.post_execute"


@dataclass
class Plugin:
    """A registered plugin with metadata and hooks."""
    name: str
    version: str
    description: str
    author: str
    enabled: bool = True
    hooks: Dict[HookPoint, List[Callable]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    last_modified: float = 0.0
    
    def register_hook(self, hook_point: HookPoint, handler: Callable):
        """Register a handler for a hook point."""
        if hook_point not in self.hooks:
            self.hooks[hook_point] = []
        self.hooks[hook_point].append(handler)
    
    def execute_hooks(self, hook_point: HookPoint, *args, **kwargs) -> List[Any]:
        """Execute all handlers for a hook point."""
        results = []
        if not self.enabled:
            return results
        for handler in self.hooks.get(hook_point, []):
            try:
                result = handler(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(f"Plugin '{self.name}' hook {hook_point.value} failed: {e}")
        return results


def plugin(name: str = None, version: str = "1.0.0", description: str = "", author: str = ""):
    """Decorator to register a class or function as a plugin.
    
    Usage (class-based):
        @plugin(name="my_plugin", version="1.0.0", description="Does something")
        class MyPlugin:
            def on_startup(self):
                ...
    
    Usage (function-based):
        @plugin(name="my_plugin")
        def my_plugin():
            # Returns a dict of hooks
            return {
                HookPoint.SYSTEM_STARTUP: lambda: print("started"),
            }
    """
    def decorator(cls_or_func):
        plugin_name = name or getattr(cls_or_func, "__name__", "unknown")
        
        registry = PluginRegistry.get_instance()
        
        # Create plugin instance
        p = Plugin(
            name=plugin_name,
            version=version,
            description=description,
            author=author,
        )
        
        if inspect.isclass(cls_or_func):
            # Class-based plugin
            instance = cls_or_func()
            p.instance = instance
            
            # Auto-discover hook methods
            for hook_point in HookPoint:
                method_name = f"on_{hook_point.value.replace('.', '_')}"
                if hasattr(instance, method_name):
                    p.register_hook(hook_point, getattr(instance, method_name))
            
            # Also check for generic on_hook method
            if hasattr(instance, "on_hook"):
                for hook_point in HookPoint:
                    p.register_hook(hook_point, lambda *a, hp=hook_point, inst=instance: inst.on_hook(hp, *a))
        
        elif callable(cls_or_func):
            # Function-based: call it to get hooks dict
            try:
                hooks = cls_or_func()
                if isinstance(hooks, dict):
                    for hook_point, handler in hooks.items():
                        if isinstance(hook_point, str):
                            hook_point = HookPoint(hook_point)
                        p.register_hook(hook_point, handler)
            except Exception as e:
                logger.warning(f"Plugin function {plugin_name} failed to initialize: {e}")
        
        registry.register(p)
        return cls_or_func
    
    return decorator


class PluginRegistry:
    """Central registry for all plugins."""
    
    _instance: Optional["PluginRegistry"] = None
    
    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._hook_manager = HookManager()
        self._plugins_dir: Optional[Path] = None
        self._file_times: Dict[str, float] = {}
    
    @classmethod
    def get_instance(cls) -> "PluginRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def register(self, plugin: Plugin) -> Plugin:
        """Register a plugin."""
        self._plugins[plugin.name] = plugin
        # Register hooks with hook manager
        for hook_point, handlers in plugin.hooks.items():
            for handler in handlers:
                self._hook_manager.register(hook_point, handler, plugin.name)
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
        return plugin
    
    def unregister(self, name: str):
        """Unregister a plugin."""
        if name in self._plugins:
            plugin = self._plugins.pop(name)
            for hook_point in plugin.hooks:
                self._hook_manager.unregister_all(hook_point, name)
            logger.info(f"Unregistered plugin: {name}")
    
    def get(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def list_plugins(self, enabled_only: bool = False) -> List[Plugin]:
        """List all registered plugins."""
        plugins = list(self._plugins.values())
        if enabled_only:
            plugins = [p for p in plugins if p.enabled]
        return plugins
    
    def set_enabled(self, name: str, enabled: bool):
        """Enable or disable a plugin."""
        p = self._plugins.get(name)
        if p:
            p.enabled = enabled
            if enabled:
                # Re-register hooks
                for hook_point, handlers in p.hooks.items():
                    for handler in handlers:
                        self._hook_manager.register(hook_point, handler, p.name)
            else:
                # Unregister hooks
                for hook_point in p.hooks:
                    self._hook_manager.unregister_all(hook_point, p.name)
    
    def execute_hook(self, hook_point: HookPoint, *args, **kwargs) -> List[Any]:
        """Execute all handlers for a hook point across all plugins."""
        return self._hook_manager.execute(hook_point, *args, **kwargs)
    
    def load_plugins_from_directory(self, directory: str):
        """Load all plugins from a directory."""
        self._plugins_dir = Path(directory)
        if not self._plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {directory}")
            return
        
        for file_path in self._plugins_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            self._load_plugin_file(file_path)
    
    def _load_plugin_file(self, file_path: Path):
        """Load a single plugin file."""
        try:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            module = importlib.util.module_from_spec(spec)
            
            # Add plugins dir to path for imports
            if self._plugins_dir and str(self._plugins_dir) not in sys.path:
                sys.path.insert(0, str(self._plugins_dir))
            
            spec.loader.exec_module(module)
            
            # Update file modification time
            mtime = file_path.stat().st_mtime
            self._file_times[str(file_path)] = mtime
            
            # Mark plugin with file path
            for plugin in self._plugins.values():
                if not plugin.file_path:
                    plugin.file_path = str(file_path)
                    plugin.last_modified = mtime
            
            logger.info(f"Loaded plugin file: {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {file_path}: {e}")
    
    def check_hot_reload(self):
        """Check for modified plugin files and reload them."""
        if not self._plugins_dir:
            return
        
        for file_path in self._plugins_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            current_mtime = file_path.stat().st_mtime
            last_mtime = self._file_times.get(str(file_path), 0)
            
            if current_mtime > last_mtime:
                logger.info(f"Plugin file modified, reloading: {file_path.name}")
                
                # Find plugins from this file and unregister them
                plugins_to_remove = [p.name for p in self._plugins.values() if p.file_path == str(file_path)]
                for name in plugins_to_remove:
                    self.unregister(name)
                
                # Reload
                self._load_plugin_file(file_path)
                self._file_times[str(file_path)] = current_mtime
    
    def get_stats(self) -> Dict[str, Any]:
        """Get plugin registry statistics."""
        total = len(self._plugins)
        enabled = sum(1 for p in self._plugins.values() if p.enabled)
        hooks = {}
        for p in self._plugins.values():
            for hp in p.hooks:
                hooks[hp.value] = hooks.get(hp.value, 0) + len(p.hooks[hp])
        
        return {
            "total_plugins": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "hooks_by_point": hooks,
            "plugins_dir": str(self._plugins_dir) if self._plugins_dir else None,
        }


class HookManager:
    """Manages hook registrations and execution."""
    
    def __init__(self):
        self._handlers: Dict[HookPoint, List[Tuple[str, Callable]]] = {}
    
    def register(self, hook_point: HookPoint, handler: Callable, plugin_name: str):
        """Register a handler for a hook point."""
        if hook_point not in self._handlers:
            self._handlers[hook_point] = []
        self._handlers[hook_point].append((plugin_name, handler))
    
    def unregister_all(self, hook_point: HookPoint, plugin_name: str):
        """Unregister all handlers from a plugin for a hook point."""
        if hook_point in self._handlers:
            self._handlers[hook_point] = [
                (pn, h) for pn, h in self._handlers[hook_point] if pn != plugin_name
            ]
    
    def execute(self, hook_point: HookPoint, *args, **kwargs) -> List[Any]:
        """Execute all handlers for a hook point."""
        results = []
        registry = PluginRegistry.get_instance()
        
        for plugin_name, handler in self._handlers.get(hook_point, []):
            plugin = registry.get(plugin_name)
            if plugin and not plugin.enabled:
                continue
            try:
                result = handler(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(f"Hook {hook_point.value} in plugin '{plugin_name}' failed: {e}")
                logger.debug(traceback.format_exc())
        
        return results
    
    def list_hooks(self) -> Dict[str, List[str]]:
        """List all registered hooks by point."""
        return {
            hp.value: [pn for pn, _ in handlers]
            for hp, handlers in self._handlers.items()
        }


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return PluginRegistry.get_instance()


# Convenience function for executing hooks
def execute_hook(hook_point: HookPoint, *args, **kwargs) -> List[Any]:
    """Execute all handlers for a hook point."""
    return PluginRegistry.get_instance().execute_hook(hook_point, *args, **kwargs)
