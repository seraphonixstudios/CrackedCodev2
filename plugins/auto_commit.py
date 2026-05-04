"""Auto Commit Plugin - Automatically commits successful autonomous production.

When the autonomous producer finishes generating a project, this plugin
automatically stages all files and creates a descriptive git commit.
"""

import subprocess
from pathlib import Path

from src.plugin_system import plugin, HookPoint


@plugin(
    name="auto_commit",
    version="1.0.0",
    description="Auto-commit after successful autonomous production",
    author="CrackedCode Team"
)
class AutoCommitPlugin:
    """Auto-commits generated projects with descriptive messages."""
    
    def on_orchestrator_task_completed(self, task):
        """Check if this was an autonomous production task and commit."""
        task_type = getattr(task, 'intent', '')
        if task_type != 'autonomous':
            return None
        
        # Try to find the output directory from task metadata
        metadata = getattr(task, 'metadata', {}) or {}
        output_dir = metadata.get('output_dir', '.')
        
        if not Path(output_dir).exists():
            return None
        
        try:
            # Stage all files
            subprocess.run(
                ["git", "add", "."],
                cwd=output_dir,
                capture_output=True,
                timeout=10
            )
            
            # Create commit
            result = subprocess.run(
                ["git", "commit", "-m", "Autonomous production output"],
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return f"[AutoCommit] Committed changes in {output_dir}"
            else:
                return f"[AutoCommit] Nothing to commit or commit failed"
        except Exception as e:
            return f"[AutoCommit] Error: {e}"
