"""Model Fine-tuning Pipeline v2.10.0 - Local model fine-tuning with Ollama.

Prepare training data from conversations, code reviews, and agent outputs.
Create a custom Ollama model with a Modelfile for domain-specific tasks.

Usage:
    from src.model_finetune import get_finetune_pipeline
    pipeline = get_finetune_pipeline()
    
    # Prepare data from conversations
    pipeline.prepare_from_conversations(".crackedcode/memory")
    
    # Create custom model
    pipeline.create_model("crackedcode-custom", base_model="qwen3:8b")
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("ModelFinetune")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class TrainingExample:
    """A single training example for fine-tuning."""
    instruction: str
    input_text: str = ""
    output_text: str = ""
    system_prompt: str = ""
    category: str = "general"  # code, chat, review, security, debug
    quality_score: float = 1.0
    source: str = ""


@dataclass
class TrainingDataset:
    """A dataset for model fine-tuning."""
    name: str
    examples: List[TrainingExample] = field(default_factory=list)
    categories: Dict[str, int] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinetuneJob:
    """A fine-tuning job."""
    id: str
    model_name: str
    base_model: str
    status: str = "pending"  # pending, preparing, training, completed, failed
    dataset_path: str = ""
    modelfile_path: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration: float = 0.0
    error: str = ""


# ── Fine-tuning Pipeline ───────────────────────────────────────────────────

class FinetunePipeline:
    """Local model fine-tuning pipeline with Ollama."""
    
    SYSTEM_PROMPTS = {
        "code": "You are an expert programmer. Write clean, efficient, well-documented code.",
        "chat": "You are a helpful AI assistant. Provide clear, accurate, and friendly responses.",
        "review": "You are a senior code reviewer. Identify issues and suggest improvements.",
        "security": "You are a security engineer. Identify vulnerabilities and suggest fixes.",
        "debug": "You are a debugging expert. Find root causes and provide solutions.",
        "general": "You are CrackedCode, a local AI coding assistant. Help with software engineering tasks.",
    }
    
    def __init__(self, data_dir: str = ".crackedcode/finetune"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, FinetuneJob] = {}
    
    def prepare_from_conversations(self, memory_dir: str,
                                    min_quality: float = 0.7) -> TrainingDataset:
        """Prepare training data from conversation history."""
        dataset = TrainingDataset(name="conversations")
        memory_path = Path(memory_dir)
        
        if not memory_path.exists():
            logger.warning(f"Memory directory not found: {memory_dir}")
            return dataset
        
        # Load conversations
        conversations_file = memory_path / "conversations.json"
        if conversations_file.exists():
            try:
                with open(conversations_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for conv in data.get("conversations", []):
                    messages = conv.get("messages", [])
                    if len(messages) < 2:
                        continue
                    
                    # Pair user/assistant messages
                    for i in range(0, len(messages) - 1, 2):
                        if messages[i].get("role") == "user" and messages[i + 1].get("role") == "assistant":
                            example = TrainingExample(
                                instruction=messages[i].get("content", ""),
                                output_text=messages[i + 1].get("content", ""),
                                system_prompt=conv.get("system_prompt", self.SYSTEM_PROMPTS["general"]),
                                category=self._categorize(messages[i].get("content", "")),
                                quality_score=conv.get("quality_score", 1.0),
                                source="conversation",
                            )
                            
                            if example.quality_score >= min_quality:
                                dataset.examples.append(example)
                                dataset.categories[example.category] = dataset.categories.get(example.category, 0) + 1
            except Exception as e:
                logger.error(f"Failed to load conversations: {e}")
        
        # Load memories
        memories_file = memory_path / "memories.json"
        if memories_file.exists():
            try:
                with open(memories_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for mem in data.get("memories", []):
                    content = mem.get("content", "")
                    if content:
                        example = TrainingExample(
                            instruction=f"Recall: {mem.get('topic', 'information')}",
                            output_text=content,
                            category="general",
                            quality_score=0.8,
                            source="memory",
                        )
                        dataset.examples.append(example)
                        dataset.categories[example.category] = dataset.categories.get(example.category, 0) + 1
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")
        
        logger.info(f"Prepared {len(dataset.examples)} training examples from conversations")
        return dataset
    
    def prepare_from_codebase(self, repo_path: str = ".",
                               file_types: Optional[List[str]] = None) -> TrainingDataset:
        """Prepare training data from codebase (docstrings, comments, implementations)."""
        dataset = TrainingDataset(name="codebase")
        
        if file_types is None:
            file_types = [".py", ".js", ".ts", ".java", ".go", ".rs"]
        
        repo = Path(repo_path)
        
        for ext in file_types:
            for file_path in repo.rglob(f"*{ext}"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Extract docstrings and function definitions
                    examples = self._extract_code_examples(content, ext)
                    for ex in examples:
                        dataset.examples.append(ex)
                        dataset.categories[ex.category] = dataset.categories.get(ex.category, 0) + 1
                
                except Exception as e:
                    logger.debug(f"Failed to read {file_path}: {e}")
        
        logger.info(f"Prepared {len(dataset.examples)} training examples from codebase")
        return dataset
    
    def _extract_code_examples(self, content: str, ext: str) -> List[TrainingExample]:
        """Extract training examples from code content."""
        examples = []
        
        if ext == ".py":
            # Extract Python docstrings
            import re
            
            # Function definitions with docstrings
            func_pattern = r'def\s+(\w+)\s*\([^)]*\):\s*"""(.*?)"""'
            for match in re.finditer(func_pattern, content, re.DOTALL):
                func_name = match.group(1)
                docstring = match.group(2).strip()
                
                examples.append(TrainingExample(
                    instruction=f"Explain the function {func_name}",
                    output_text=docstring,
                    category="code",
                    source="docstring",
                ))
            
            # Class definitions with docstrings
            class_pattern = r'class\s+(\w+)[^:]*:\s*"""(.*?)"""'
            for match in re.finditer(class_pattern, content, re.DOTALL):
                class_name = match.group(1)
                docstring = match.group(2).strip()
                
                examples.append(TrainingExample(
                    instruction=f"Explain the class {class_name}",
                    output_text=docstring,
                    category="code",
                    source="docstring",
                ))
        
        return examples
    
    def _categorize(self, text: str) -> str:
        """Categorize a conversation message."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["security", "vulnerability", "attack", "auth", "encrypt"]):
            return "security"
        elif any(word in text_lower for word in ["bug", "error", "fix", "debug", "trace"]):
            return "debug"
        elif any(word in text_lower for word in ["review", "refactor", "clean", "quality"]):
            return "review"
        elif any(word in text_lower for word in ["code", "function", "class", "implement", "write"]):
            return "code"
        else:
            return "chat"
    
    def export_dataset(self, dataset: TrainingDataset,
                       format: str = "jsonl") -> str:
        """Export dataset to training format."""
        timestamp = int(time.time())
        filename = f"{dataset.name}_{timestamp}.{format}"
        filepath = self.data_dir / filename
        
        if format == "jsonl":
            with open(filepath, "w", encoding="utf-8") as f:
                for ex in dataset.examples:
                    obj = {
                        "instruction": ex.instruction,
                        "input": ex.input_text,
                        "output": ex.output_text,
                        "system": ex.system_prompt,
                    }
                    f.write(json.dumps(obj) + "\n")
        
        elif format == "alpaca":
            data = []
            for ex in dataset.examples:
                data.append({
                    "instruction": ex.instruction,
                    "input": ex.input_text,
                    "output": ex.output_text,
                })
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
        elif format == "sharegpt":
            data = []
            for ex in dataset.examples:
                data.append({
                    "conversations": [
                        {"from": "system", "value": ex.system_prompt},
                        {"from": "human", "value": ex.instruction},
                        {"from": "gpt", "value": ex.output_text},
                    ]
                })
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
        logger.info(f"Exported dataset to {filepath}")
        return str(filepath)
    
    def create_model(self, model_name: str, base_model: str = "qwen3:8b",
                     dataset_path: Optional[str] = None,
                     system_prompt: Optional[str] = None) -> FinetuneJob:
        """Create a custom Ollama model with a Modelfile."""
        from datetime import datetime
        import hashlib
        
        job_id = hashlib.md5(f"{model_name}_{time.time()}".encode()).hexdigest()[:12]
        started_at = datetime.utcnow().isoformat()
        
        job = FinetuneJob(
            id=job_id,
            model_name=model_name,
            base_model=base_model,
            status="preparing",
            started_at=started_at,
        )
        self.jobs[job_id] = job
        
        # Generate Modelfile
        modelfile_content = self._generate_modelfile(
            base_model=base_model,
            system_prompt=system_prompt or self.SYSTEM_PROMPTS["general"],
            dataset_path=dataset_path,
        )
        
        modelfile_path = self.data_dir / f"Modelfile.{model_name}"
        with open(modelfile_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)
        
        job.modelfile_path = str(modelfile_path)
        
        # Create Ollama model
        try:
            job.status = "training"
            result = subprocess.run(
                ["ollama", "create", model_name, "-f", str(modelfile_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode == 0:
                job.status = "completed"
                job.completed_at = datetime.utcnow().isoformat()
                logger.info(f"Successfully created model: {model_name}")
            else:
                job.status = "failed"
                job.error = result.stderr
                logger.error(f"Model creation failed: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            job.status = "failed"
            job.error = "Model creation timed out"
            logger.error("Model creation timed out")
        except FileNotFoundError:
            job.status = "failed"
            job.error = "Ollama not found. Is it installed and in PATH?"
            logger.error("Ollama command not found")
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error(f"Model creation error: {e}")
        
        job.duration = time.time() - datetime.fromisoformat(started_at).timestamp()
        return job
    
    def _generate_modelfile(self, base_model: str,
                            system_prompt: str,
                            dataset_path: Optional[str] = None) -> str:
        """Generate a Modelfile for Ollama."""
        content = f"FROM {base_model}\n\n"
        content += f'SYSTEM """{system_prompt}"""\n\n'
        content += "PARAMETER temperature 0.7\n"
        content += "PARAMETER top_p 0.9\n"
        content += "PARAMETER top_k 40\n"
        
        if dataset_path and Path(dataset_path).exists():
            content += f"\n# Training data\nADAPTER {dataset_path}\n"
        
        return content
    
    def list_jobs(self) -> List[FinetuneJob]:
        """List all fine-tuning jobs."""
        return list(self.jobs.values())
    
    def get_job(self, job_id: str) -> Optional[FinetuneJob]:
        """Get a fine-tuning job by ID."""
        return self.jobs.get(job_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        total_jobs = len(self.jobs)
        completed = sum(1 for j in self.jobs.values() if j.status == "completed")
        failed = sum(1 for j in self.jobs.values() if j.status == "failed")
        
        return {
            "total_jobs": total_jobs,
            "completed": completed,
            "failed": failed,
            "pending": total_jobs - completed - failed,
            "data_dir": str(self.data_dir),
        }


def get_finetune_pipeline(data_dir: str = ".crackedcode/finetune") -> FinetunePipeline:
    """Get the global fine-tuning pipeline."""
    return FinetunePipeline(data_dir=data_dir)

