import re


credential_patterns = [
    re.compile(r"(?P<login>[\w.+-]+@[\w.-]+\.\w+)\s*-{2,}\s*(?P<password>\S{4,})", re.IGNORECASE),
    re.compile(r"(?P<login>[\w.+-]+@[\w.-]+\.\w+)\s*[:;|/ ]\s*(?P<password>\S{4,})", re.IGNORECASE),
    re.compile(r"(?:login|логин)\s*[:\-]\s*(?P<login>\S+).{0,40}(?:pass|password|пароль)\s*[:\-]\s*(?P<password>\S+)", re.IGNORECASE | re.DOTALL),
]


def extract_credentials(message: str) -> str | None:
    for pattern in credential_patterns:
        match = pattern.search(message)
        if match:
            return f"{match.group('login')}:{match.group('password')}"
    return None
