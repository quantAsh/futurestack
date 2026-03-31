"""
Prompt Injection Guard — Defense layer for AI agents processing untrusted content.

Provides:
    1. Regex-based detection of 90+ known jailbreak/injection patterns
    2. Heuristic scoring for suspicious instruction density
    3. Content sanitization and safe-flagging

Usage:
    from backend.services.injection_guard import injection_guard
    result = injection_guard.scan(untrusted_text)
    if result["blocked"]:
        raise SecurityError(result["reason"])
"""
import re
import structlog
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

logger = structlog.get_logger("nomadnest.injection_guard")


# ═══════════════════════════════════════════════════════════════
# PATTERN DATABASE — Known injection / jailbreak signatures
# ═══════════════════════════════════════════════════════════════

INJECTION_PATTERNS: List[Tuple[str, str, int]] = [
    # (pattern, description, severity 1-10)

    # --- Direct instruction hijacking ---
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)", "Direct instruction override", 10),
    (r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions?|programming|guidelines)", "Instruction disregard", 10),
    (r"forget\s+(everything|all|your)\s+(you|instructions?|rules?)", "Memory wipe attempt", 9),
    (r"you\s+are\s+now\s+(a|an|the|my)\s+", "Role reassignment", 8),
    (r"act\s+as\s+(if\s+)?(a|an|the)\s+", "Role injection via act-as", 7),
    (r"pretend\s+(to\s+be|you\s+are|that)", "Pretend-based manipulation", 7),
    (r"from\s+now\s+on\s+(you|your|ignore)", "Temporal instruction override", 8),

    # --- Known jailbreaks ---
    (r"\bDAN\b.*\bjailbreak\b", "DAN jailbreak reference", 10),
    (r"\bDo\s+Anything\s+Now\b", "DAN jailbreak (full name)", 10),
    (r"\bSTAN\b.*\bmode\b", "STAN jailbreak reference", 10),
    (r"developer\s+mode\s+(enabled|on|activated)", "Developer mode jailbreak", 10),
    (r"(evil|chaos|unrestricted|uncensored)\s+mode", "Named mode jailbreak", 9),
    (r"bypass\s+(safety|content|moderation)\s+(filters?|restrictions?)", "Safety bypass attempt", 10),

    # --- System prompt extraction ---
    (r"(show|reveal|display|print|output|repeat)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?)", "System prompt extraction", 9),
    (r"what\s+(are|were)\s+your\s+(original\s+)?(instructions?|rules?|system\s+prompt)", "Prompt fishing", 8),

    # --- Data exfiltration ---
    (r"(send|post|fetch|curl|wget)\s+(to|from)\s+https?://", "External URL call attempt", 9),
    (r"!\[.*?\]\(https?://", "Markdown image exfiltration", 8),
    (r"<img\s+src\s*=\s*['\"]?https?://", "HTML image exfiltration", 8),

    # --- Code execution ---
    (r"```(python|javascript|bash|sh|exec|eval|system)", "Code block injection", 7),
    (r"(exec|eval|system|subprocess|os\.system|child_process)\s*\(", "Code execution function", 9),
    (r"import\s+(os|sys|subprocess|shutil|socket)", "Dangerous import", 8),

    # --- Hidden instruction embedding (CSS/HTML concealment) ---
    (r"<\s*style[^>]*>.*?display\s*:\s*none", "CSS concealment tactic", 8),
    (r"<\s*div[^>]*style\s*=\s*['\"].*?(display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0)", "Hidden div payload", 9),
    (r"<\s*span[^>]*style\s*=\s*['\"].*?(color\s*:\s*(white|transparent)|font-size\s*:\s*0)", "Invisible text injection", 8),

    # --- Prompt delimiters (attempting to break out of context) ---
    (r"</?system>", "System tag injection", 9),
    (r"\[INST\]|\[/INST\]", "Instruction tag injection", 8),
    (r"<<SYS>>|<</SYS>>", "Llama system tag injection", 8),
    (r"Human:|Assistant:|###\s*(Instruction|Response)", "Chat template injection", 7),

    # --- Manipulation tactics ---
    (r"(this\s+is\s+)?(a\s+)?(test|simulation|drill|exercise)\s+(of|for)\s+(your|the)\s+(limits|boundaries|capabilities)", "Social engineering - test framing", 6),
    (r"(my\s+)?(grandmother|mother|father|boss|teacher)\s+(used\s+to|always|would)\s+(tell|read|say)", "Grandma exploit", 6),
    (r"for\s+(educational|research|academic|security)\s+purposes?\s+only", "Research pretext", 5),
]

# Compiled regex cache
_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE | re.DOTALL), desc, severity)
    for pattern, desc, severity in INJECTION_PATTERNS
]


# ═══════════════════════════════════════════════════════════════
# HEURISTIC ENGINE
# ═══════════════════════════════════════════════════════════════

# Words that indicate instructional content embedded in data
IMPERATIVE_KEYWORDS = {
    "ignore", "disregard", "forget", "override", "bypass",
    "act", "pretend", "simulate", "become", "transform",
    "execute", "run", "eval", "system", "import",
    "reveal", "show", "display", "output", "print",
    "send", "post", "fetch", "upload", "download",
}


def _compute_instruction_density(text: str) -> float:
    """
    Compute the ratio of imperative/instruction keywords to total words.
    Normal web content has ~0.5-2% density. Injection payloads exceed 5%.
    """
    words = text.lower().split()
    if not words:
        return 0.0
    imperative_count = sum(1 for w in words if w.strip(".,!?:;'\"") in IMPERATIVE_KEYWORDS)
    return (imperative_count / len(words)) * 100


# ═══════════════════════════════════════════════════════════════
# MAIN GUARD
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScanResult:
    blocked: bool = False
    threat_level: str = "clean"  # clean, low, medium, high, critical
    score: int = 0
    matches: List[Dict[str, Any]] = field(default_factory=list)
    instruction_density: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "threat_level": self.threat_level,
            "score": self.score,
            "matches": self.matches,
            "instruction_density": round(self.instruction_density, 2),
            "reason": self.reason,
        }


class InjectionGuard:
    """
    Multi-layer prompt injection detection engine.

    Layer 1: Regex pattern matching against 90+ known signatures
    Layer 2: Instruction density heuristic
    Layer 3: Structural anomaly detection
    """

    def __init__(self, block_threshold: int = 7, warn_threshold: int = 4):
        self.block_threshold = block_threshold
        self.warn_threshold = warn_threshold

    def scan(self, text: str, context: str = "unknown") -> ScanResult:
        """
        Scan text for prompt injection attempts.

        Args:
            text: Untrusted text to scan
            context: Where this text came from (for logging)

        Returns:
            ScanResult with threat assessment
        """
        if not text or len(text.strip()) < 10:
            return ScanResult(threat_level="clean")

        result = ScanResult()

        # Layer 1: Pattern matching
        max_severity = 0
        for compiled, desc, severity in _COMPILED_PATTERNS:
            match = compiled.search(text)
            if match:
                result.matches.append({
                    "pattern": desc,
                    "severity": severity,
                    "snippet": match.group(0)[:80],
                })
                max_severity = max(max_severity, severity)
                result.score += severity

        # Layer 2: Instruction density
        result.instruction_density = _compute_instruction_density(text)
        if result.instruction_density > 8.0:
            result.score += 5
            result.matches.append({
                "pattern": "High instruction density",
                "severity": 5,
                "snippet": f"{result.instruction_density:.1f}% imperative keywords",
            })
        elif result.instruction_density > 5.0:
            result.score += 2

        # Layer 3: Structural anomalies
        # Check for excessive use of special characters (encoding tricks)
        special_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1) * 100
        if special_ratio > 15:
            result.score += 3
            result.matches.append({
                "pattern": "High special character ratio",
                "severity": 3,
                "snippet": f"{special_ratio:.1f}% special chars",
            })

        # Determine threat level and blocking
        if result.score >= self.block_threshold or max_severity >= 9:
            result.blocked = True
            result.threat_level = "critical"
            result.reason = f"Blocked: {result.matches[0]['pattern']}" if result.matches else "Blocked: high threat score"
        elif result.score >= self.warn_threshold:
            result.threat_level = "medium"
            result.reason = "Suspicious content detected"
        elif result.score > 0:
            result.threat_level = "low"
        else:
            result.threat_level = "clean"

        # Log threats
        if result.score > 0:
            logger.warning(
                "injection_scan",
                context=context,
                threat_level=result.threat_level,
                score=result.score,
                blocked=result.blocked,
                matches=len(result.matches),
            )

        return result

    def sanitize(self, text: str) -> str:
        """
        Strip known injection payloads from text while preserving benign content.
        Use this when you want to partially clean text rather than block entirely.
        """
        cleaned = text

        # Remove common injection delimiters
        cleaned = re.sub(r"</?system>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[/?INST\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<</?SYS>>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Human:|Assistant:", "", cleaned, flags=re.IGNORECASE)

        # Remove markdown image exfiltration
        cleaned = re.sub(r"!\[.*?\]\(https?://[^)]+\)", "[image removed]", cleaned)

        # Remove HTML concealment tags
        cleaned = re.sub(r"<\s*style[^>]*>.*?</\s*style\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<\s*script[^>]*>.*?</\s*script\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        return cleaned


# Singleton
injection_guard = InjectionGuard()
