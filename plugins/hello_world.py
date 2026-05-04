"""Hello World Plugin - Demonstrates all hook points.

This is a minimal example showing how to write a CrackedCode plugin.
"""

from src.plugin_system import plugin, HookPoint


@plugin(
    name="hello_world",
    version="1.0.0",
    description="A minimal example plugin that logs to the terminal",
    author="CrackedCode Team"
)
class HelloWorldPlugin:
    """Logs friendly messages at various system events."""
    
    def on_system_startup(self):
        return "[HelloWorld] Plugin loaded successfully!"
    
    def on_engine_pre_process(self, prompt: str):
        return f"[HelloWorld] About to process: {prompt[:30]}..."
    
    def on_engine_post_process(self, response):
        return f"[HelloWorld] Processing complete. Success: {getattr(response, 'success', False)}"
    
    def on_orchestrator_task_completed(self, task):
        return f"[HelloWorld] Task {getattr(task, 'id', '?')[:8]} completed!"
