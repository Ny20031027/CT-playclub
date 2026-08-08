"""
Utility to detect and fix common MySQL charset encoding issues.
When Chinese text appears garbled, it's usually because UTF-8 bytes
were stored or read with the wrong connection charset.
"""
import re


def fix_mojibake(text):
    """
    Try to fix common double-encoding issues with Chinese text.
    
    Common scenarios:
    1. UTF-8 bytes stored as latin1 → read as latin1, encode back, decode as utf-8
    2. GBK bytes stored as latin1 → read as latin1, encode back, decode as gbk
    """
    if not text or not isinstance(text, str):
        return text
    
    # If text already looks like valid Chinese, return as-is
    if _looks_healthy(text):
        return text
    
    # Try latin1 → utf-8 (most common: UTF-8 bytes mis-stored as latin1)
    try:
        fixed = text.encode('latin1').decode('utf-8')
        if _looks_healthy(fixed):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    # Try latin1 → gbk
    try:
        fixed = text.encode('latin1').decode('gbk')
        if _looks_healthy(fixed):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    # Try utf-8 → latin1 → utf-8 (reverse double encoding)
    try:
        intermediate = text.encode('utf-8').decode('latin1')
        if _looks_healthy(intermediate):
            return intermediate
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    # Try cp1252 → utf-8
    try:
        fixed = text.encode('cp1252').decode('utf-8')
        if _looks_healthy(fixed):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    return text


def _looks_healthy(text):
    """Check if text contains recognizable Chinese characters and no obvious garbage."""
    if not text:
        return False
    
    # Check: does it have at least some Chinese characters?
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
    
    # Check: doesn't have too many replacement characters or control chars
    replacement_count = text.count('\ufffd')
    if replacement_count > len(text) * 0.3:
        return False
    
    # If it has Chinese characters, it's probably healthy
    if has_chinese:
        return True
    
    # If no Chinese expected (e.g., English name), check for common garbled patterns
    # Garbled Chinese often produces characters like: Â, Ã, ©, «, etc.
    garbled_pattern = re.search(r'[\u00c0-\u00ff]{3,}', text)
    if garbled_pattern:
        return False
    
    return True
