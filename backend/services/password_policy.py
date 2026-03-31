"""
Password Policy - Enforce password strength requirements.
"""
import re
from typing import Tuple, List
from dataclasses import dataclass


@dataclass
class PasswordPolicy:
    """Configurable password policy."""
    min_length: int = 8
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    special_characters: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    disallow_common: bool = True
    disallow_username: bool = True


# Common passwords to reject (top 100 most common)
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "passw0rd", "shadow", "123123", "654321", "superman",
    "qazwsx", "michael", "football", "password1", "password123", "welcome",
    "welcome1", "admin", "login", "starwars", "hello", "charlie", "donald",
    "password!", "!@#$%^&*", "p@ssw0rd", "admin123", "root", "toor",
}


class PasswordValidator:
    """Validates passwords against configurable policy."""
    
    def __init__(self, policy: PasswordPolicy = None):
        self.policy = policy or PasswordPolicy()
    
    def validate(
        self,
        password: str,
        username: str = None,
        email: str = None,
    ) -> Tuple[bool, List[str]]:
        """
        Validate a password against the policy.
        
        Args:
            password: The password to validate
            username: Optional username to check against
            email: Optional email to check against
        
        Returns:
            (is_valid, list of violation messages)
        """
        violations = []
        
        # Length checks
        if len(password) < self.policy.min_length:
            violations.append(f"Password must be at least {self.policy.min_length} characters")
        
        if len(password) > self.policy.max_length:
            violations.append(f"Password must be at most {self.policy.max_length} characters")
        
        # Character requirements
        if self.policy.require_uppercase and not re.search(r"[A-Z]", password):
            violations.append("Password must contain at least one uppercase letter")
        
        if self.policy.require_lowercase and not re.search(r"[a-z]", password):
            violations.append("Password must contain at least one lowercase letter")
        
        if self.policy.require_digit and not re.search(r"\d", password):
            violations.append("Password must contain at least one digit")
        
        if self.policy.require_special:
            special_pattern = f"[{re.escape(self.policy.special_characters)}]"
            if not re.search(special_pattern, password):
                violations.append("Password must contain at least one special character")
        
        # Common password check
        if self.policy.disallow_common:
            if password.lower() in COMMON_PASSWORDS:
                violations.append("Password is too common, please choose a more unique password")
        
        # Username/email check
        if self.policy.disallow_username:
            if username and username.lower() in password.lower():
                violations.append("Password cannot contain your username")
            
            if email:
                email_name = email.split("@")[0].lower()
                if len(email_name) > 3 and email_name in password.lower():
                    violations.append("Password cannot contain your email address")
        
        return (len(violations) == 0, violations)
    
    def get_strength(self, password: str) -> dict:
        """
        Calculate password strength score.
        
        Returns:
            Dict with score (0-100), label, and feedback
        """
        score = 0
        feedback = []
        
        # Length scoring (up to 30 points)
        length = len(password)
        if length >= 8:
            score += 10
        if length >= 12:
            score += 10
        if length >= 16:
            score += 10
        
        # Character diversity (up to 40 points)
        if re.search(r"[a-z]", password):
            score += 10
        if re.search(r"[A-Z]", password):
            score += 10
        if re.search(r"\d", password):
            score += 10
        if re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
            score += 10
        
        # Variety of characters (up to 20 points)
        unique_chars = len(set(password))
        if unique_chars >= 6:
            score += 10
        if unique_chars >= 10:
            score += 10
        
        # Penalties
        if password.lower() in COMMON_PASSWORDS:
            score = min(score, 10)
            feedback.append("This is a commonly used password")
        
        if re.match(r"^[a-zA-Z]+$", password):
            score -= 10
            feedback.append("Consider adding numbers or symbols")
        
        if re.match(r"^\d+$", password):
            score -= 20
            feedback.append("Password should not be only numbers")
        
        # Ensure score is in range
        score = max(0, min(100, score))
        
        # Label
        if score < 30:
            label = "weak"
        elif score < 50:
            label = "fair"
        elif score < 70:
            label = "good"
        elif score < 90:
            label = "strong"
        else:
            label = "excellent"
        
        # Add positive feedback
        if not feedback:
            if score >= 70:
                feedback.append("Good password!")
            elif score >= 50:
                feedback.append("Consider making it longer")
        
        return {
            "score": score,
            "label": label,
            "feedback": feedback,
        }


# Default validator instance
password_validator = PasswordValidator()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def validate_password(
    password: str,
    username: str = None,
    email: str = None,
) -> Tuple[bool, List[str]]:
    """Validate password against default policy."""
    return password_validator.validate(password, username, email)


def get_password_strength(password: str) -> dict:
    """Get password strength score."""
    return password_validator.get_strength(password)


def check_password_requirements(password: str) -> dict:
    """Check if password meets all requirements and get detailed feedback."""
    is_valid, violations = validate_password(password)
    strength = get_password_strength(password)
    
    return {
        "is_valid": is_valid,
        "violations": violations,
        "strength": strength,
    }
