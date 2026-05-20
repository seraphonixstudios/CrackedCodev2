"""Adaptive Learning Engine v2.10.0 - Learns from user feedback and corrections.

Captures explicit feedback (thumbs up/down), implicit signals (edits, retries),
and explicit corrections to build a persistent user profile. Automatically injects
relevant learned context into prompts for personalized responses.

Storage:
    .crackedcode/learning/profile.json   - User profile (preferences, corrections, style)
    .crackedcode/learning/feedback.jsonl - Append-only feedback event log

Features:
- Feedback recording with rating (-1, 0, +1)
- Correction tracking (original -> corrected)
- Explicit preference management
- Rule-based preference inference from feedback history
- Topic tracking and style indicator extraction
- Relevance-scored context injection into prompts
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

from src.logger_config import get_logger

logger = get_logger("AdaptiveLearning")


@dataclass
class UserPreference:
    """A learned or explicitly set user preference."""
    key: str
    value: str
    confidence: float = 0.5
    source: str = "inferred"  # "explicit", "inferred", "corrected"
    context: str = ""
    timestamp: float = field(default_factory=time.time)
    frequency: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreference":
        return cls(**data)


@dataclass
class Correction:
    """An explicit user correction to a previous response."""
    original: str
    corrected: str
    context: str = ""
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Correction":
        return cls(**data)


@dataclass
class FeedbackEvent:
    """A single feedback instance from the user."""
    prompt: str
    response: str
    rating: int  # -1 (bad), 0 (neutral), 1 (good)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackEvent":
        return cls(**data)


@dataclass
class UserProfile:
    """Complete learned user profile."""
    preferences: List[UserPreference] = field(default_factory=list)
    corrections: List[Correction] = field(default_factory=list)
    feedback_count: int = 0
    topics: Dict[str, int] = field(default_factory=dict)
    style_indicators: Dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preferences": [p.to_dict() for p in self.preferences],
            "corrections": [c.to_dict() for c in self.corrections],
            "feedback_count": self.feedback_count,
            "topics": self.topics,
            "style_indicators": self.style_indicators,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(
            preferences=[UserPreference.from_dict(p) for p in data.get("preferences", [])],
            corrections=[Correction.from_dict(c) for c in data.get("corrections", [])],
            feedback_count=data.get("feedback_count", 0),
            topics=data.get("topics", {}),
            style_indicators=data.get("style_indicators", {}),
            created_at=data.get("created_at", time.time()),
            last_updated=data.get("last_updated", time.time()),
        )


class LearningStore:
    """Persistent storage for adaptive learning data."""

    def __init__(self, base_path: str = ".crackedcode/learning"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.base_path / "profile.json"
        self.feedback_path = self.base_path / "feedback.jsonl"

    def save_profile(self, profile: UserProfile) -> None:
        """Save user profile to JSON."""
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save learning profile: {e}")

    def load_profile(self) -> UserProfile:
        """Load user profile from JSON, or return empty profile."""
        if not self.profile_path.exists():
            return UserProfile()
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserProfile.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to load learning profile: {e}, starting fresh")
            return UserProfile()

    def append_feedback(self, event: FeedbackEvent) -> None:
        """Append a feedback event to the JSONL log."""
        try:
            with open(self.feedback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to append feedback: {e}")

    def get_feedback_history(self, limit: int = 100) -> List[FeedbackEvent]:
        """Read recent feedback events from the JSONL log."""
        if not self.feedback_path.exists():
            return []
        events = []
        try:
            with open(self.feedback_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(FeedbackEvent.from_dict(json.loads(line)))
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            logger.error(f"Failed to read feedback history: {e}")
        return events[-limit:]

    def get_all_feedback(self) -> List[FeedbackEvent]:
        """Read all feedback events."""
        return self.get_feedback_history(limit=100000)


class AdaptiveLearningEngine:
    """Main engine for learning from user interactions.

    Captures feedback, corrections, and explicit preferences to build a
    persistent user profile. Injects relevant learned context into prompts.
    """

    # Topic keyword mappings for simple extraction
    TOPIC_KEYWORDS: Dict[str, List[str]] = {
        "python": ["python", "py", "pip", "django", "flask", "fastapi", "pandas", "numpy"],
        "javascript": ["javascript", "js", "node", "npm", "react", "vue", "angular", "typescript", "ts"],
        "web": ["html", "css", "web", "frontend", "backend", "api", "http", "rest", "graphql"],
        "database": ["sql", "database", "postgres", "sqlite", "mongodb", "redis", "orm"],
        "devops": ["docker", "kubernetes", "k8s", "ci/cd", "deploy", "aws", "azure", "gcp", "terraform"],
        "testing": ["test", "pytest", "unittest", "jest", "cypress", "selenium"],
        "security": ["security", "auth", "oauth", "jwt", "encrypt", "vulnerability", "pentest"],
        "mobile": ["android", "ios", "flutter", "react native", "swift", "kotlin"],
        "ai_ml": ["machine learning", "ml", "ai", "neural", "pytorch", "tensorflow", "llm"],
    }

    # Style indicators and their extraction rules
    STYLE_RULES = {
        "verbosity": {
            "high_threshold": 2500,
            "low_threshold": 500,
            "step": 0.15,
        },
        "code_examples": {
            "pattern": "```",
            "threshold": 2,
            "step": 0.2,
        },
        "explanations": {
            "pattern": "because",
            "threshold": 3,
            "step": 0.15,
        },
    }

    def __init__(self, store: Optional[LearningStore] = None):
        self.store = store or LearningStore()
        self.profile = self.store.load_profile()
        self._feedback_buffer: List[FeedbackEvent] = []
        self._loaded = True

    # ------------------------------------------------------------------ #
    # Public API: Recording
    # ------------------------------------------------------------------ #

    def record_feedback(self, prompt: str, response: str, rating: int, metadata: Optional[Dict] = None) -> None:
        """Record user feedback on a prompt-response pair.

        Args:
            prompt: The user's original prompt
            response: The AI's response
            rating: -1 (bad), 0 (neutral), 1 (good)
            metadata: Optional extra data (intent, model, etc.)
        """
        event = FeedbackEvent(
            prompt=prompt,
            response=response,
            rating=rating,
            metadata=metadata or {},
        )
        self._feedback_buffer.append(event)
        self.store.append_feedback(event)
        self.profile.feedback_count += 1
        self.profile.last_updated = time.time()

        # Extract topics from the prompt
        topics = self._extract_topics(prompt)
        for topic in topics:
            self.profile.topics[topic] = self.profile.topics.get(topic, 0) + 1

        # Periodically run inference
        if len(self._feedback_buffer) >= 5:
            self.extract_preferences()
            self._feedback_buffer.clear()

        self._save_profile()
        logger.info(f"Recorded feedback: rating={rating}, total_feedback={self.profile.feedback_count}")

    def record_correction(self, original: str, corrected: str, context: str = "", reason: str = "") -> None:
        """Record an explicit user correction.

        Args:
            original: The AI's original (wrong) response snippet
            corrected: What it should have been
            context: The surrounding conversation context
            reason: Why the correction was needed
        """
        correction = Correction(
            original=original,
            corrected=corrected,
            context=context,
            reason=reason,
        )
        self.profile.corrections.append(correction)
        self.profile.last_updated = time.time()

        # Infer a preference from the correction
        self._infer_preference_from_correction(correction)

        self._save_profile()
        logger.info(f"Recorded correction: '{original[:50]}...' -> '{corrected[:50]}...'")

    def add_explicit_preference(self, key: str, value: str, context: str = "") -> None:
        """Add an explicitly stated user preference.

        Args:
            key: Preference category (e.g., "code_style", "verbosity", "language")
            value: The preference value
            context: Optional context for when this applies
        """
        # Update existing preference if same key/value
        for pref in self.profile.preferences:
            if pref.key == key and pref.value == value:
                pref.frequency += 1
                pref.confidence = min(1.0, pref.confidence + 0.1)
                pref.timestamp = time.time()
                self._save_profile()
                return

        # Add new preference
        pref = UserPreference(
            key=key,
            value=value,
            confidence=0.9,
            source="explicit",
            context=context,
        )
        self.profile.preferences.append(pref)
        self._save_profile()
        logger.info(f"Added explicit preference: {key}={value}")

    # ------------------------------------------------------------------ #
    # Public API: Inference
    # ------------------------------------------------------------------ #

    def extract_preferences(self) -> List[UserPreference]:
        """Analyze feedback history to infer new preferences.

        Returns:
            List of newly inferred preferences
        """
        history = self.store.get_feedback_history(limit=50)
        if len(history) < 3:
            return []

        new_prefs: List[UserPreference] = []

        positive = [e for e in history if e.rating == 1]
        negative = [e for e in history if e.rating == -1]

        # Infer verbosity preference
        self._infer_verbosity(positive, negative)

        # Infer code example preference
        self._infer_code_examples(positive, negative)

        # Infer explanation depth
        self._infer_explanations(positive, negative)

        self._save_profile()
        return new_prefs

    # ------------------------------------------------------------------ #
    # Public API: Context Injection
    # ------------------------------------------------------------------ #

    def get_context_for_prompt(self, prompt: str, max_prefs: int = 5) -> str:
        """Generate a context block of learned preferences relevant to the prompt.

        Args:
            prompt: The current user prompt
            max_prefs: Maximum number of preferences to include

        Returns:
            Formatted context string, or empty string if no relevant preferences
        """
        if not self.profile.preferences and not self.profile.corrections:
            return ""

        lines: List[str] = []

        # Score and sort preferences by relevance
        scored: List[tuple[float, UserPreference]] = []
        for pref in self.profile.preferences:
            score = self._relevance_score(prompt, f"{pref.key} {pref.value} {pref.context}")
            scored.append((score * pref.confidence, pref))

        scored.sort(key=lambda x: x[0], reverse=True)

        for score, pref in scored[:max_prefs]:
            if score > 0.2:  # Minimum relevance threshold
                lines.append(f"- {pref.key}: {pref.value}")

        # Add relevant recent corrections
        for corr in self.profile.corrections[-3:]:
            if self._relevance_score(prompt, corr.context) > 0.5:
                lines.append(
                    f"- CORRECTION: Instead of '{corr.original[:60]}', "
                    f"use '{corr.corrected[:60]}'"
                )
                if corr.reason:
                    lines.append(f"  Reason: {corr.reason}")

        # Add style indicators if strong enough
        for style, value in self.profile.style_indicators.items():
            if abs(value) >= 0.5:
                direction = "more" if value > 0 else "less"
                lines.append(f"- Style: User prefers {direction} {style}")

        if not lines:
            return ""

        return (
            "[USER PREFERENCES - learned from past interactions]\n"
            + "\n".join(lines)
            + "\n[/USER PREFERENCES]\n"
        )

    def get_user_profile(self) -> UserProfile:
        """Return the current user profile."""
        return self.profile

    def get_stats(self) -> Dict[str, Any]:
        """Return learning engine statistics."""
        top_topics = dict(
            sorted(self.profile.topics.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        return {
            "preferences_count": len(self.profile.preferences),
            "corrections_count": len(self.profile.corrections),
            "feedback_count": self.profile.feedback_count,
            "topics": top_topics,
            "style_indicators": self.profile.style_indicators,
            "last_updated": self.profile.last_updated,
        }

    def reset_profile(self) -> None:
        """Reset the user profile (clear all learned data)."""
        self.profile = UserProfile()
        self._feedback_buffer.clear()
        self._save_profile()
        logger.info("User profile reset")

    # ------------------------------------------------------------------ #
    # Private: Inference Helpers
    # ------------------------------------------------------------------ #

    def _infer_verbosity(self, positive: List[FeedbackEvent], negative: List[FeedbackEvent]) -> None:
        """Infer verbosity preference from feedback."""
        rules = self.STYLE_RULES["verbosity"]
        if positive:
            avg_len = sum(len(e.response) for e in positive) / len(positive)
            if avg_len > rules["high_threshold"]:
                self.profile.style_indicators["verbosity"] = (
                    self.profile.style_indicators.get("verbosity", 0) + rules["step"]
                )
        if negative:
            avg_len = sum(len(e.response) for e in negative) / len(negative)
            if avg_len > rules["high_threshold"] * 1.5:
                self.profile.style_indicators["verbosity"] = (
                    self.profile.style_indicators.get("verbosity", 0) - rules["step"]
                )
            elif avg_len < rules["low_threshold"]:
                self.profile.style_indicators["verbosity"] = (
                    self.profile.style_indicators.get("verbosity", 0) + rules["step"]
                )

    def _infer_code_examples(self, positive: List[FeedbackEvent], negative: List[FeedbackEvent]) -> None:
        """Infer code example preference from feedback."""
        rules = self.STYLE_RULES["code_examples"]
        pattern = rules["pattern"]

        pos_count = sum(1 for e in positive if pattern in e.response)
        neg_count = sum(1 for e in negative if pattern in e.response)

        if len(positive) > 0 and pos_count / len(positive) > 0.6:
            self.profile.style_indicators["code_examples"] = (
                self.profile.style_indicators.get("code_examples", 0) + rules["step"]
            )
        if len(negative) > 0 and neg_count / len(negative) > 0.6:
            self.profile.style_indicators["code_examples"] = (
                self.profile.style_indicators.get("code_examples", 0) - rules["step"]
            )

    def _infer_explanations(self, positive: List[FeedbackEvent], negative: List[FeedbackEvent]) -> None:
        """Infer explanation depth preference from feedback."""
        rules = self.STYLE_RULES["explanations"]
        pattern = rules["pattern"]

        pos_count = sum(1 for e in positive if pattern in e.response.lower())
        neg_count = sum(1 for e in negative if pattern in e.response.lower())

        if len(positive) > 0 and pos_count / len(positive) > 0.5:
            self.profile.style_indicators["explanations"] = (
                self.profile.style_indicators.get("explanations", 0) + rules["step"]
            )
        if len(negative) > 0 and neg_count / len(negative) > 0.5:
            self.profile.style_indicators["explanations"] = (
                self.profile.style_indicators.get("explanations", 0) - rules["step"]
            )

    def _infer_preference_from_correction(self, correction: Correction) -> None:
        """Infer a preference from a user correction."""
        # Simple keyword-based inference
        corr_lower = correction.corrected.lower()
        if "use" in corr_lower or "prefer" in corr_lower:
            # Try to extract a preference statement
            parts = correction.corrected.split("use ", 1)
            if len(parts) == 2:
                value = parts[1].split(".")[0].split(",")[0].strip()
                if len(value) > 3:
                    self.profile.preferences.append(UserPreference(
                        key="style",
                        value=value,
                        confidence=0.7,
                        source="corrected",
                        context=correction.context,
                    ))

    # ------------------------------------------------------------------ #
    # Status Report (for GUI panel)
    # ------------------------------------------------------------------ #

    def get_formatted_report(self) -> Dict[str, Any]:
        """Return a structured status report for the learning panel."""
        profile = self.profile
        top_topics = dict(
            sorted(profile.topics.items(), key=lambda x: x[1], reverse=True)[:8]
        )

        # Categorize preferences
        explicit_prefs = [
            {"key": p.key, "value": p.value, "confidence": p.confidence, "source": p.source, "context": p.context}
            for p in profile.preferences if p.source == "explicit"
        ]
        inferred_prefs = [
            {"key": p.key, "value": p.value, "confidence": p.confidence, "source": p.source, "context": p.context}
            for p in profile.preferences if p.source != "explicit"
        ]

        corrections = [
            {"original": c.original[:100], "corrected": c.corrected[:100], "context": c.context, "reason": c.reason}
            for c in profile.corrections[-10:]
        ]

        # Style description
        verbosity = profile.style_indicators.get("verbosity", 0.0)
        code_examples = profile.style_indicators.get("code_examples", 0.0)

        return {
            "enabled": True,
            "feedback_count": profile.feedback_count,
            "preferences_count": len(profile.preferences),
            "preferences_explicit": explicit_prefs,
            "preferences_inferred": inferred_prefs,
            "corrections_count": len(profile.corrections),
            "corrections": corrections,
            "topics": top_topics,
            "style": {
                "verbosity": verbosity,
                "verbosity_label": self._style_label(verbosity),
                "code_examples": code_examples,
                "code_examples_label": self._style_label(code_examples),
            },
            "created_at": profile.created_at,
            "last_updated": profile.last_updated,
        }

    def _style_label(self, value: float) -> str:
        if value > 0.5:
            return "high"
        elif value < -0.5:
            return "low"
        return "neutral"

    # ------------------------------------------------------------------ #
    # Private: Utilities
    # ------------------------------------------------------------------ #

    def _save_profile(self) -> None:
        """Persist profile to disk."""
        self.store.save_profile(self.profile)

    def _relevance_score(self, prompt: str, text: str) -> float:
        """Calculate keyword overlap relevance score."""
        prompt_words: Set[str] = set(w.lower() for w in prompt.split() if len(w) > 2)
        text_words: Set[str] = set(w.lower() for w in text.split() if len(w) > 2)
        if not prompt_words or not text_words:
            return 0.0
        overlap = len(prompt_words & text_words)
        return overlap / max(len(prompt_words), len(text_words))

    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text using keyword matching."""
        text_lower = text.lower()
        topics: List[str] = []
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        return topics


# -------------------------------------------------------------------------- #
# Singleton
# -------------------------------------------------------------------------- #

_adaptive_engine: Optional[AdaptiveLearningEngine] = None


def get_adaptive_learning_engine(store: Optional[LearningStore] = None) -> AdaptiveLearningEngine:
    """Get or create the global AdaptiveLearningEngine singleton."""
    global _adaptive_engine
    if _adaptive_engine is None:
        _adaptive_engine = AdaptiveLearningEngine(store)
    return _adaptive_engine


def reset_adaptive_learning_engine() -> None:
    """Reset the global singleton (for testing)."""
    global _adaptive_engine
    _adaptive_engine = None
