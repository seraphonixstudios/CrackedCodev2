"""Agent Reasoning Engine - Full thought process and coherence tracking.

Provides chain-of-thought reasoning for all agent decisions, enabling:
- Transparent decision-making with step-by-step logic
- Confidence scoring with evidence tracking
- Cross-agent coherence measurement and maintenance
- Self-correction reasoning with hypothesis testing
- Contextual memory for reasoning continuity

Architecture:
    ReasoningStep -> ThoughtChain -> AgentReasoning -> CoherenceTracker
"""

import time
import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Set, Tuple
from datetime import datetime

from src.logger_config import get_logger

logger = get_logger("AgentReasoning")


class ReasoningType(Enum):
    """Types of reasoning steps."""
    OBSERVATION = "observation"
    ANALYSIS = "analysis"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    ACTION = "action"
    REFLECTION = "reflection"
    CORRECTION = "correction"
    INFERENCE = "inference"


class ConfidenceLevel(Enum):
    """Confidence levels for reasoning steps."""
    VERY_LOW = 0.0
    LOW = 0.25
    MEDIUM = 0.5
    HIGH = 0.75
    VERY_HIGH = 1.0


@dataclass
class ReasoningStep:
    """A single step in an agent's reasoning chain.
    
    Attributes:
        id: Unique step identifier
        type: Type of reasoning (observation, analysis, decision, etc.)
        content: The actual thought/reasoning text
        confidence: Confidence score 0.0-1.0
        evidence: Supporting evidence or data
        timestamp: When this step was recorded
        source: Which agent/component produced this step
        related_steps: IDs of related reasoning steps
        metadata: Additional context
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ReasoningType = ReasoningType.OBSERVATION
    content: str = ""
    confidence: float = 0.5
    evidence: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    related_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize step to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "source": self.source,
            "related_steps": self.related_steps,
            "metadata": self.metadata,
        }


@dataclass
class ThoughtChain:
    """A complete chain of reasoning for a single decision or action.
    
    Represents the full thought process from initial observation to final
    decision, with intermediate analysis, hypotheses, and reflections.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    context: str = ""
    steps: List[ReasoningStep] = field(default_factory=list)
    final_decision: str = ""
    final_confidence: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    
    def add_step(
        self,
        content: str,
        step_type: ReasoningType = ReasoningType.OBSERVATION,
        confidence: float = 0.5,
        evidence: List[str] = None,
        source: str = "unknown",
        metadata: Dict[str, Any] = None,
    ) -> ReasoningStep:
        """Add a reasoning step to the chain.
        
        Args:
            content: The reasoning content
            step_type: Type of reasoning step
            confidence: Confidence level (0.0-1.0)
            evidence: Supporting evidence
            source: Source agent/component
            metadata: Additional metadata
            
        Returns:
            The created ReasoningStep
        """
        step = ReasoningStep(
            type=step_type,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence or [],
            source=source,
            metadata=metadata or {},
        )
        
        # Link to previous step if exists
        if self.steps:
            step.related_steps.append(self.steps[-1].id)
        
        self.steps.append(step)
        return step
    
    def add_observation(self, content: str, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add an observation step."""
        return self.add_step(content, ReasoningType.OBSERVATION, 0.8, evidence, source)
    
    def add_analysis(self, content: str, confidence: float = 0.6, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add an analysis step."""
        return self.add_step(content, ReasoningType.ANALYSIS, confidence, evidence, source)
    
    def add_hypothesis(self, content: str, confidence: float = 0.5, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add a hypothesis step."""
        return self.add_step(content, ReasoningType.HYPOTHESIS, confidence, evidence, source)
    
    def add_decision(self, content: str, confidence: float = 0.7, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add a decision step."""
        step = self.add_step(content, ReasoningType.DECISION, confidence, evidence, source)
        self.final_decision = content
        self.final_confidence = confidence
        self.completed_at = time.time()
        return step
    
    def add_action(self, content: str, confidence: float = 0.8, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add an action step."""
        return self.add_step(content, ReasoningType.ACTION, confidence, evidence, source)
    
    def add_reflection(self, content: str, confidence: float = 0.6, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add a reflection step."""
        return self.add_step(content, ReasoningType.REFLECTION, confidence, evidence, source)
    
    def add_correction(self, content: str, reason: str, confidence: float = 0.7, source: str = "unknown") -> ReasoningStep:
        """Add a correction step with reason."""
        return self.add_step(
            content, ReasoningType.CORRECTION, confidence,
            evidence=[reason], source=source,
            metadata={"correction_reason": reason}
        )
    
    def add_inference(self, content: str, confidence: float = 0.6, evidence: List[str] = None, source: str = "unknown") -> ReasoningStep:
        """Add an inference step."""
        return self.add_step(content, ReasoningType.INFERENCE, confidence, evidence, source)
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all steps."""
        if not self.steps:
            return 0.0
        return sum(s.confidence for s in self.steps) / len(self.steps)
    
    @property
    def decision_confidence(self) -> float:
        """Get the confidence of the final decision."""
        decision_steps = [s for s in self.steps if s.type == ReasoningType.DECISION]
        if decision_steps:
            return decision_steps[-1].confidence
        return self.final_confidence
    
    @property
    def coherence_score(self) -> float:
        """Calculate internal coherence of the reasoning chain.
        
        Measures how well the steps logically connect:
        - Observation -> Analysis: good
        - Analysis -> Hypothesis: good
        - Hypothesis -> Decision: good
        - Decision -> Action: good
        - Low confidence after high confidence: penalty
        """
        if len(self.steps) < 2:
            return 1.0
        
        score = 1.0
        type_flow = {
            ReasoningType.OBSERVATION: [ReasoningType.ANALYSIS, ReasoningType.INFERENCE],
            ReasoningType.ANALYSIS: [ReasoningType.HYPOTHESIS, ReasoningType.DECISION, ReasoningType.INFERENCE],
            ReasoningType.HYPOTHESIS: [ReasoningType.DECISION, ReasoningType.ANALYSIS, ReasoningType.TESTING if hasattr(ReasoningType, 'TESTING') else ReasoningType.ACTION],
            ReasoningType.DECISION: [ReasoningType.ACTION, ReasoningType.REFLECTION],
            ReasoningType.ACTION: [ReasoningType.OBSERVATION, ReasoningType.REFLECTION],
            ReasoningType.REFLECTION: [ReasoningType.CORRECTION, ReasoningType.DECISION, ReasoningType.ANALYSIS],
            ReasoningType.CORRECTION: [ReasoningType.ACTION, ReasoningType.DECISION],
            ReasoningType.INFERENCE: [ReasoningType.HYPOTHESIS, ReasoningType.DECISION, ReasoningType.ANALYSIS],
        }
        
        for i in range(1, len(self.steps)):
            prev = self.steps[i - 1]
            curr = self.steps[i]
            
            # Check logical flow
            valid_next = type_flow.get(prev.type, [])
            if curr.type not in valid_next:
                score -= 0.05
            
            # Check confidence consistency
            if curr.confidence < prev.confidence - 0.4:
                score -= 0.1
            
            # Check evidence linkage
            if prev.evidence and not any(e in curr.evidence for e in prev.evidence):
                score -= 0.02
        
        return max(0.0, min(1.0, score))
    
    def get_summary(self) -> str:
        """Get a text summary of the reasoning chain."""
        lines = [f"Thought Chain: {self.title}"]
        lines.append(f"Context: {self.context}")
        lines.append(f"Steps: {len(self.steps)} | Avg Confidence: {self.average_confidence:.2f} | Coherence: {self.coherence_score:.2f}")
        lines.append("")
        
        for i, step in enumerate(self.steps, 1):
            confidence_bar = "█" * int(step.confidence * 10) + "░" * (10 - int(step.confidence * 10))
            lines.append(f"  {i}. [{step.type.value.upper():12}] [{confidence_bar}] {step.confidence:.2f}")
            lines.append(f"     {step.content}")
            if step.evidence:
                lines.append(f"     Evidence: {', '.join(step.evidence[:3])}")
            lines.append("")
        
        if self.final_decision:
            lines.append(f"  → DECISION: {self.final_decision} (confidence: {self.final_confidence:.2f})")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize thought chain to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "steps": [s.to_dict() for s in self.steps],
            "final_decision": self.final_decision,
            "final_confidence": round(self.final_confidence, 3),
            "average_confidence": round(self.average_confidence, 3),
            "coherence_score": round(self.coherence_score, 3),
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None,
            "tags": self.tags,
        }


@dataclass
class AgentReasoning:
    """Complete reasoning state for an agent.
    
    Maintains all thought chains, current context, and reasoning memory
    for a single agent instance.
    """
    agent_id: str = ""
    agent_role: str = ""
    thought_chains: List[ThoughtChain] = field(default_factory=list)
    current_chain: Optional[ThoughtChain] = None
    reasoning_memory: List[Dict[str, Any]] = field(default_factory=list)
    max_memory: int = 50
    
    def start_chain(self, title: str, context: str = "", tags: List[str] = None) -> ThoughtChain:
        """Start a new thought chain.
        
        Args:
            title: Description of what this chain is reasoning about
            context: Initial context for the reasoning
            tags: Categorical tags for this chain
            
        Returns:
            The new ThoughtChain
        """
        chain = ThoughtChain(
            title=title,
            context=context,
            tags=tags or [],
        )
        chain.add_observation(f"Starting reasoning: {title}", source=self.agent_role)
        if context:
            chain.add_observation(f"Context: {context}", source=self.agent_role)
        
        self.current_chain = chain
        self.thought_chains.append(chain)
        
        # Prune old chains if too many
        if len(self.thought_chains) > self.max_memory:
            self.thought_chains = self.thought_chains[-self.max_memory:]
        
        return chain
    
    def end_chain(self, final_decision: str = "", confidence: float = 0.0):
        """End the current thought chain with a final decision.
        
        Args:
            final_decision: The final decision made
            confidence: Confidence in the decision
        """
        if self.current_chain:
            self.current_chain.add_decision(
                final_decision, confidence, source=self.agent_role
            )
            self._store_to_memory(self.current_chain)
            self.current_chain = None
    
    def add_step(self, content: str, step_type: ReasoningType = ReasoningType.OBSERVATION,
                 confidence: float = 0.5, evidence: List[str] = None):
        """Add a step to the current chain."""
        if self.current_chain:
            self.current_chain.add_step(content, step_type, confidence, evidence, self.agent_role)
    
    def observe(self, content: str, evidence: List[str] = None):
        """Record an observation."""
        if self.current_chain:
            self.current_chain.add_observation(content, evidence, self.agent_role)
    
    def analyze(self, content: str, confidence: float = 0.6, evidence: List[str] = None):
        """Record an analysis."""
        if self.current_chain:
            self.current_chain.add_analysis(content, confidence, evidence, self.agent_role)
    
    def decide(self, content: str, confidence: float = 0.7, evidence: List[str] = None):
        """Record a decision."""
        if self.current_chain:
            self.current_chain.add_decision(content, confidence, evidence, self.agent_role)
            self._store_to_memory(self.current_chain)
    
    def reflect(self, content: str, confidence: float = 0.6):
        """Record a reflection."""
        if self.current_chain:
            self.current_chain.add_reflection(content, confidence, source=self.agent_role)
    
    def correct(self, content: str, reason: str, confidence: float = 0.7):
        """Record a correction."""
        if self.current_chain:
            self.current_chain.add_correction(content, reason, confidence, self.agent_role)
    
    def infer(self, content: str, confidence: float = 0.6, evidence: List[str] = None):
        """Record an inference."""
        if self.current_chain:
            self.current_chain.add_inference(content, confidence, evidence, self.agent_role)
    
    def _store_to_memory(self, chain: ThoughtChain):
        """Store chain summary to memory."""
        self.reasoning_memory.append({
            "chain_id": chain.id,
            "title": chain.title,
            "decision": chain.final_decision,
            "confidence": chain.final_confidence,
            "coherence": chain.coherence_score,
            "timestamp": chain.completed_at or time.time(),
            "tags": chain.tags,
        })
        
        if len(self.reasoning_memory) > self.max_memory:
            self.reasoning_memory = self.reasoning_memory[-self.max_memory:]
    
    def get_recent_memory(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get recent reasoning memory entries."""
        return self.reasoning_memory[-n:]
    
    def get_chain_by_id(self, chain_id: str) -> Optional[ThoughtChain]:
        """Get a thought chain by ID."""
        for chain in self.thought_chains:
            if chain.id == chain_id:
                return chain
        return None
    
    def get_chains_by_tag(self, tag: str) -> List[ThoughtChain]:
        """Get all chains with a specific tag."""
        return [c for c in self.thought_chains if tag in c.tags]
    
    @property
    def total_steps(self) -> int:
        """Total reasoning steps across all chains."""
        return sum(len(c.steps) for c in self.thought_chains)
    
    @property
    def average_coherence(self) -> float:
        """Average coherence across all chains."""
        if not self.thought_chains:
            return 1.0
        return sum(c.coherence_score for c in self.thought_chains) / len(self.thought_chains)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent reasoning state."""
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "total_chains": len(self.thought_chains),
            "total_steps": self.total_steps,
            "average_coherence": round(self.average_coherence, 3),
            "current_chain": self.current_chain.to_dict() if self.current_chain else None,
            "memory_entries": len(self.reasoning_memory),
        }


class CoherenceTracker:
    """Tracks coherence between multiple agents.
    
    Measures how well agents' reasoning aligns and identifies
    conflicts or gaps in collective reasoning.
    """
    
    def __init__(self):
        self.agent_reasonings: Dict[str, AgentReasoning] = {}
        self.shared_context: Dict[str, Any] = {}
        self.conflict_log: List[Dict[str, Any]] = []
        self.consensus_points: List[Dict[str, Any]] = []
    
    def register_agent(self, agent_id: str, agent_role: str):
        """Register an agent for coherence tracking."""
        if agent_id not in self.agent_reasonings:
            self.agent_reasonings[agent_id] = AgentReasoning(
                agent_id=agent_id,
                agent_role=agent_role,
            )
            logger.info(f"Registered agent {agent_id} ({agent_role}) for coherence tracking")
    
    def get_agent_reasoning(self, agent_id: str) -> Optional[AgentReasoning]:
        """Get an agent's reasoning state."""
        return self.agent_reasonings.get(agent_id)
    
    def update_shared_context(self, key: str, value: Any):
        """Update shared context that all agents can reference."""
        old_value = self.shared_context.get(key)
        self.shared_context[key] = value
        
        if old_value is not None and old_value != value:
            logger.info(f"Shared context updated: {key}")
    
    def measure_cross_agent_coherence(self) -> Dict[str, Any]:
        """Measure coherence across all registered agents.
        
        Returns metrics including:
        - Overall coherence score
        - Agent-specific coherence scores
        - Identified conflicts
        - Consensus points
        """
        if len(self.agent_reasonings) < 2:
            return {
                "overall_coherence": 1.0,
                "agent_count": len(self.agent_reasonings),
                "conflicts": 0,
                "consensus": 0,
            }
        
        # Collect recent decisions from all agents
        recent_decisions = {}
        for agent_id, reasoning in self.agent_reasonings.items():
            memory = reasoning.get_recent_memory(3)
            if memory:
                recent_decisions[agent_id] = memory[-1]
        
        # Measure decision alignment
        coherence_scores = []
        conflicts = []
        
        agent_ids = list(recent_decisions.keys())
        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                id1, id2 = agent_ids[i], agent_ids[j]
                dec1 = recent_decisions[id1]
                dec2 = recent_decisions[id2]
                
                # Check if decisions are related (same tags)
                tags1 = set(dec1.get("tags", []))
                tags2 = set(dec2.get("tags", []))
                
                if tags1 & tags2:  # Common tags
                    conf1 = dec1.get("confidence", 0.5)
                    conf2 = dec2.get("confidence", 0.5)
                    
                    # High confidence in opposite directions = conflict
                    if abs(conf1 - conf2) > 0.5 and conf1 > 0.7 and conf2 > 0.7:
                        conflicts.append({
                            "agent1": id1,
                            "agent2": id2,
                            "decision1": dec1.get("decision", ""),
                            "decision2": dec2.get("decision", ""),
                            "severity": "high" if abs(conf1 - conf2) > 0.8 else "medium",
                        })
                    
                    coherence_scores.append(1.0 - abs(conf1 - conf2))
        
        overall = sum(coherence_scores) / len(coherence_scores) if coherence_scores else 1.0
        
        return {
            "overall_coherence": round(overall, 3),
            "agent_count": len(self.agent_reasonings),
            "conflicts": len(conflicts),
            "conflict_details": conflicts,
            "consensus": len(self.consensus_points),
            "decision_alignment": round(sum(coherence_scores) / len(coherence_scores), 3) if coherence_scores else 1.0,
        }
    
    def identify_conflicts(self) -> List[Dict[str, Any]]:
        """Identify reasoning conflicts between agents."""
        return self.conflict_log
    
    def record_consensus(self, topic: str, agreeing_agents: List[str], decision: str):
        """Record a consensus point between agents."""
        self.consensus_points.append({
            "topic": topic,
            "agents": agreeing_agents,
            "decision": decision,
            "timestamp": time.time(),
        })
    
    def get_reasoning_summary(self) -> Dict[str, Any]:
        """Get a summary of all agent reasoning."""
        agent_summaries = {}
        for agent_id, reasoning in self.agent_reasonings.items():
            agent_summaries[agent_id] = {
                "role": reasoning.agent_role,
                "chains": len(reasoning.thought_chains),
                "steps": reasoning.total_steps,
                "coherence": round(reasoning.average_coherence, 3),
                "recent_decisions": [
                    {
                        "title": m["title"],
                        "decision": m["decision"],
                        "confidence": m["confidence"],
                    }
                    for m in reasoning.get_recent_memory(3)
                ],
            }
        
        coherence = self.measure_cross_agent_coherence()
        
        return {
            "agents": agent_summaries,
            "cross_agent_coherence": coherence,
            "shared_context_keys": list(self.shared_context.keys()),
            "total_conflicts": len(self.conflict_log),
            "total_consensus": len(self.consensus_points),
        }


class ReasoningEngine:
    """Central reasoning engine that coordinates reasoning across the system.
    
    Provides factory methods for creating contextual reasoning chains
    and maintains the global coherence tracker.
    """
    
    def __init__(self):
        self.coherence_tracker = CoherenceTracker()
        self.global_reasoning_log: List[Dict[str, Any]] = []
        self.max_log_size = 1000
        self._reasoning_callbacks: List[Callable[[Dict[str, Any]], None]] = []
    
    def register_agent(self, agent_id: str, agent_role: str) -> AgentReasoning:
        """Register an agent and return its reasoning handle."""
        self.coherence_tracker.register_agent(agent_id, agent_role)
        return self.coherence_tracker.get_agent_reasoning(agent_id)
    
    def create_reasoning_chain(
        self,
        agent_id: str,
        title: str,
        context: str = "",
        tags: List[str] = None,
    ) -> Optional[ThoughtChain]:
        """Create a new reasoning chain for an agent.
        
        Args:
            agent_id: The agent's unique ID
            title: What is being reasoned about
            context: Initial context
            tags: Categorical tags
            
        Returns:
            The new ThoughtChain or None if agent not found
        """
        reasoning = self.coherence_tracker.get_agent_reasoning(agent_id)
        if reasoning:
            chain = reasoning.start_chain(title, context, tags)
            self._log_reasoning_event("chain_started", {
                "agent_id": agent_id,
                "chain_id": chain.id,
                "title": title,
            })
            return chain
        return None
    
    def complete_reasoning_chain(self, agent_id: str, final_decision: str, confidence: float = 0.7):
        """Complete the current reasoning chain for an agent."""
        reasoning = self.coherence_tracker.get_agent_reasoning(agent_id)
        if reasoning and reasoning.current_chain:
            reasoning.end_chain(final_decision, confidence)
            self._log_reasoning_event("chain_completed", {
                "agent_id": agent_id,
                "chain_id": reasoning.thought_chains[-1].id if reasoning.thought_chains else None,
                "decision": final_decision,
                "confidence": confidence,
            })
    
    def add_reasoning_step(
        self,
        agent_id: str,
        content: str,
        step_type: ReasoningType = ReasoningType.OBSERVATION,
        confidence: float = 0.5,
        evidence: List[str] = None,
    ):
        """Add a reasoning step for an agent."""
        reasoning = self.coherence_tracker.get_agent_reasoning(agent_id)
        if reasoning:
            reasoning.add_step(content, step_type, confidence, evidence)
    
    def get_agent_thought_chain(self, agent_id: str) -> Optional[ThoughtChain]:
        """Get the current thought chain for an agent."""
        reasoning = self.coherence_tracker.get_agent_reasoning(agent_id)
        return reasoning.current_chain if reasoning else None
    
    def get_all_reasoning(self) -> Dict[str, Any]:
        """Get all reasoning data from the system."""
        return self.coherence_tracker.get_reasoning_summary()
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add a callback for reasoning events."""
        self._reasoning_callbacks.append(callback)
    
    def _log_reasoning_event(self, event_type: str, data: Dict[str, Any]):
        """Log a reasoning event and notify callbacks."""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        self.global_reasoning_log.append(event)
        
        if len(self.global_reasoning_log) > self.max_log_size:
            self.global_reasoning_log = self.global_reasoning_log[-self.max_log_size:]
        
        for callback in self._reasoning_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Reasoning callback error: {e}")
    
    def get_coherence_report(self) -> Dict[str, Any]:
        """Get a comprehensive coherence report."""
        summary = self.coherence_tracker.get_reasoning_summary()
        
        # Add recommendations
        recommendations = []
        
        if summary["cross_agent_coherence"]["overall_coherence"] < 0.5:
            recommendations.append("Low cross-agent coherence detected. Consider adding a supervisor agent to coordinate.")
        
        if summary["cross_agent_coherence"]["conflicts"] > 0:
            recommendations.append(f"{summary['cross_agent_coherence']['conflicts']} conflicts detected. Review conflict details for resolution.")
        
        for agent_id, agent_data in summary["agents"].items():
            if agent_data["coherence"] < 0.6:
                recommendations.append(f"Agent {agent_id} has low internal coherence ({agent_data['coherence']:.2f}). Review recent decisions.")
        
        summary["recommendations"] = recommendations
        return summary


# Global reasoning engine instance
_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    """Get or create the global reasoning engine."""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine


def reset_reasoning_engine():
    """Reset the global reasoning engine."""
    global _reasoning_engine
    _reasoning_engine = ReasoningEngine()
