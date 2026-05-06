"""Agent Collaboration / Multi-Agent Chat v2.9.1 - Multi-agent debate and consensus.

Multiple specialized agents (ARCHITECT, SECURITY, CODER) collaborate on a task
through structured debate. The SUPERVISOR coordinates and synthesizes consensus.

Usage:
    from src.agent_collaboration import get_agent_parliament
    parliament = get_agent_parliament()
    result = parliament.debate(
        topic="Refactor authentication module",
        agents=["architect", "security", "coder"],
        rounds=3,
    )
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("AgentCollaboration")


# ── Data Models ────────────────────────────────────────────────────────────

class AgentStance(Enum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    NEUTRAL = "neutral"
    QUESTION = "question"


@dataclass
class AgentMessage:
    """A single message from an agent in the debate."""
    agent: str
    role: str
    content: str
    stance: AgentStance = AgentStance.NEUTRAL
    confidence: float = 0.8
    references: List[str] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class DebateRound:
    """One round of multi-agent debate."""
    round_number: int
    messages: List[AgentMessage] = field(default_factory=list)
    consensus_score: float = 0.0


@dataclass
class DebateResult:
    """Result of a multi-agent debate."""
    topic: str
    rounds: List[DebateRound] = field(default_factory=list)
    final_consensus: str = ""
    consensus_score: float = 0.0
    dissents: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class AgentPersona:
    """Personality and expertise of an agent in parliament."""
    name: str
    role: str
    expertise: List[str] = field(default_factory=list)
    communication_style: str = "analytical"
    priorities: List[str] = field(default_factory=list)
    system_prompt: str = ""


# ── Agent Parliament ───────────────────────────────────────────────────────

class AgentParliament:
    """Multi-agent debate and consensus building."""
    
    PERSONAS = {
        "architect": AgentPersona(
            name="Architect",
            role="architect",
            expertise=["system design", "scalability", "patterns", "modularity"],
            communication_style="structured",
            priorities=["maintainability", "extensibility", "clean design"],
            system_prompt="You are a software architect. Focus on design patterns, scalability, and maintainability. Be concise and structured.",
        ),
        "security": AgentPersona(
            name="Security",
            role="security",
            expertise=["vulnerabilities", "crypto", "auth", "penetration testing"],
            communication_style="cautious",
            priorities=["security", "privacy", "compliance"],
            system_prompt="You are a security engineer. Identify vulnerabilities, attack vectors, and compliance issues. Be thorough and cautious.",
        ),
        "coder": AgentPersona(
            name="Coder",
            role="coder",
            expertise=["implementation", "refactoring", "performance", "testing"],
            communication_style="pragmatic",
            priorities=["performance", "readability", "test coverage"],
            system_prompt="You are a senior developer. Focus on clean code, performance, and testability. Be pragmatic and specific.",
        ),
        "reviewer": AgentPersona(
            name="Reviewer",
            role="reviewer",
            expertise=["code review", "best practices", "standards"],
            communication_style="critical",
            priorities=["code quality", "consistency", "documentation"],
            system_prompt="You are a code reviewer. Check for best practices, standards compliance, and clarity. Be critical but constructive.",
        ),
        "devops": AgentPersona(
            name="DevOps",
            role="devops",
            expertise=["deployment", "ci/cd", "containers", "monitoring"],
            communication_style="operational",
            priorities=["reliability", "automation", "observability"],
            system_prompt="You are a DevOps engineer. Consider deployment, CI/CD, monitoring, and operational concerns. Be practical.",
        ),
        "tester": AgentPersona(
            name="Tester",
            role="tester",
            expertise=["testing", "qa", "edge cases", "regression"],
            communication_style="meticulous",
            priorities=["coverage", "reliability", "edge cases"],
            system_prompt="You are a QA engineer. Identify test scenarios, edge cases, and regression risks. Be thorough and meticulous.",
        ),
    }
    
    def __init__(self, engine=None):
        self.engine = engine
    
    def debate(self, topic: str, agents: List[str], rounds: int = 3,
               context: Optional[Dict[str, Any]] = None) -> DebateResult:
        """Run a multi-agent debate on a topic."""
        start = time.time()
        debate_rounds: List[DebateRound] = []
        
        # Initialize with topic context
        current_context = f"Topic: {topic}\n"
        if context:
            for key, val in context.items():
                current_context += f"{key}: {val}\n"
        
        for round_num in range(1, rounds + 1):
            logger.info(f"Debate round {round_num}/{rounds} on: {topic}")
            debate_round = DebateRound(round_number=round_num)
            
            for agent_name in agents:
                persona = self.PERSONAS.get(agent_name)
                if not persona:
                    continue
                
                message = self._generate_agent_message(
                    persona=persona,
                    topic=topic,
                    round_num=round_num,
                    context=current_context,
                    previous_rounds=debate_rounds,
                )
                
                debate_round.messages.append(message)
                logger.info(f"  [{agent_name}] {message.stance.value}: {message.content[:80]}...")
            
            # Calculate consensus for this round
            debate_round.consensus_score = self._calculate_consensus(debate_round.messages)
            debate_rounds.append(debate_round)
            
            # Update context with this round's discussion
            current_context += f"\nRound {round_num}:\n"
            for msg in debate_round.messages:
                current_context += f"{msg.agent} ({msg.stance.value}): {msg.content}\n"
        
        # Synthesize final consensus
        final_consensus, dissents, action_items = self._synthesize_consensus(
            topic, debate_rounds, agents,
        )
        
        # Calculate overall consensus score
        consensus_score = sum(r.consensus_score for r in debate_rounds) / len(debate_rounds) if debate_rounds else 0.0
        
        return DebateResult(
            topic=topic,
            rounds=debate_rounds,
            final_consensus=final_consensus,
            consensus_score=consensus_score,
            dissents=dissents,
            action_items=action_items,
            duration=time.time() - start,
        )
    
    def _generate_agent_message(self, persona: AgentPersona, topic: str,
                                 round_num: int, context: str,
                                 previous_rounds: List[DebateRound]) -> AgentMessage:
        """Generate a message from an agent persona."""
        
        if self.engine is None:
            # Fallback: generate structured response without LLM
            return self._generate_fallback_message(persona, topic, round_num, previous_rounds)
        
        # Build prompt for the agent
        prompt = self._build_debate_prompt(persona, topic, round_num, context, previous_rounds)
        
        try:
            response = self.engine.process(
                prompt,
                system_prompt=persona.system_prompt,
            )
            
            content = response.get("response", "")
            stance = self._extract_stance(content)
            confidence = self._extract_confidence(content)
            
            return AgentMessage(
                agent=persona.name,
                role=persona.role,
                content=content,
                stance=stance,
                confidence=confidence,
                timestamp=time.time(),
            )
        except Exception as e:
            logger.error(f"Agent {persona.name} message generation failed: {e}")
            return self._generate_fallback_message(persona, topic, round_num, previous_rounds)
    
    def _build_debate_prompt(self, persona: AgentPersona, topic: str,
                             round_num: int, context: str,
                             previous_rounds: List[DebateRound]) -> str:
        """Build the debate prompt for an agent."""
        prompt = f"""You are participating in a technical debate on the following topic:

TOPIC: {topic}

YOUR ROLE: {persona.name}
YOUR EXPERTISE: {', '.join(persona.expertise)}
YOUR PRIORITIES: {', '.join(persona.priorities)}
COMMUNICATION STYLE: {persona.communication_style}

CURRENT CONTEXT:
{context}

This is round {round_num} of the debate."""
        
        if previous_rounds:
            prompt += f"\n\nPREVIOUS ROUNDS:\n"
            for r in previous_rounds:
                prompt += f"\nRound {r.round_number}:\n"
                for msg in r.messages:
                    prompt += f"- {msg.agent} ({msg.stance.value}): {msg.content[:200]}...\n"
        
        prompt += """\n
Please provide your analysis and position. Format your response as:
STANCE: [support|oppose|neutral|question]
CONFIDENCE: [0.0-1.0]
ANALYSIS: Your detailed reasoning
"""
        
        return prompt
    
    def _generate_fallback_message(self, persona: AgentPersona, topic: str,
                                    round_num: int,
                                    previous_rounds: List[DebateRound]) -> AgentMessage:
        """Generate a fallback message without LLM."""
        stances = [AgentStance.SUPPORT, AgentStance.NEUTRAL, AgentStance.QUESTION]
        stance = stances[hash(persona.name + topic) % len(stances)]
        
        content = f"As {persona.name}, I focus on {', '.join(persona.priorities[:2])}. "
        content += f"For '{topic}', my expertise in {', '.join(persona.expertise[:2])} suggests "
        
        if stance == AgentStance.SUPPORT:
            content += "this approach is sound with proper implementation."
        elif stance == AgentStance.QUESTION:
            content += "we need more details on edge cases and testing."
        else:
            content += "the approach has merit but requires careful consideration."
        
        return AgentMessage(
            agent=persona.name,
            role=persona.role,
            content=content,
            stance=stance,
            confidence=0.7,
            timestamp=time.time(),
        )
    
    def _extract_stance(self, content: str) -> AgentStance:
        """Extract stance from agent response."""
        if "STANCE:" in content:
            stance_text = content.split("STANCE:")[1].split("\n")[0].strip().lower()
            for stance in AgentStance:
                if stance.value in stance_text:
                    return stance
        return AgentStance.NEUTRAL
    
    def _extract_confidence(self, content: str) -> float:
        """Extract confidence score from agent response."""
        if "CONFIDENCE:" in content:
            try:
                conf_text = content.split("CONFIDENCE:")[1].split("\n")[0].strip()
                return max(0.0, min(1.0, float(conf_text)))
            except (ValueError, IndexError):
                pass
        return 0.8
    
    def _calculate_consensus(self, messages: List[AgentMessage]) -> float:
        """Calculate consensus score for a round."""
        if not messages:
            return 0.0
        
        # Weight by stance and confidence
        support_count = sum(1 for m in messages if m.stance == AgentStance.SUPPORT)
        oppose_count = sum(1 for m in messages if m.stance == AgentStance.OPPOSE)
        neutral_count = sum(1 for m in messages if m.stance == AgentStance.NEUTRAL)
        
        total = len(messages)
        if total == 0:
            return 0.0
        
        # Consensus = support ratio * average confidence
        avg_confidence = sum(m.confidence for m in messages) / total
        support_ratio = support_count / total
        
        # Penalize strong opposition
        opposition_penalty = oppose_count / total * 0.5
        
        return max(0.0, min(1.0, support_ratio * avg_confidence - opposition_penalty + (neutral_count / total) * 0.3))
    
    def _synthesize_consensus(self, topic: str, rounds: List[DebateRound],
                              agents: List[str]) -> tuple:
        """Synthesize final consensus from all rounds."""
        if not rounds:
            return "No consensus reached", [], []
        
        # Collect all messages
        all_messages = []
        for r in rounds:
            all_messages.extend(r.messages)
        
        # Find common themes
        support_msgs = [m for m in all_messages if m.stance == AgentStance.SUPPORT]
        oppose_msgs = [m for m in all_messages if m.stance == AgentStance.OPPOSE]
        
        # Build consensus
        consensus = f"Consensus on '{topic}':\n\n"
        
        if support_msgs:
            consensus += "Agreed points:\n"
            for m in support_msgs[:3]:
                consensus += f"- {m.agent}: {m.content[:120]}...\n"
        
        if oppose_msgs:
            consensus += "\nConcerns raised:\n"
            for m in oppose_msgs[:3]:
                consensus += f"- {m.agent}: {m.content[:120]}...\n"
        
        # Extract action items from all messages
        action_items = []
        for m in all_messages:
            if "should" in m.content.lower() or "need to" in m.content.lower() or "must" in m.content.lower():
                # Extract action sentences
                sentences = m.content.split(".")
                for s in sentences:
                    if any(word in s.lower() for word in ["should", "need to", "must", "implement", "add", "create", "fix"]):
                        action_items.append(f"[{m.agent}] {s.strip()}")
        
        # Limit action items
        action_items = list(dict.fromkeys(action_items))[:5]
        
        # Collect dissents
        dissents = [m.content[:150] for m in oppose_msgs]
        
        return consensus, dissents, action_items


def get_agent_parliament(engine=None) -> AgentParliament:
    """Get the global agent parliament."""
    return AgentParliament(engine=engine)
