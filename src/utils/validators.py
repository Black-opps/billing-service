"""
Validation utilities for payment service.
"""
import re


def validate_phone_number(phone: str) -> str:
    """
    Validate and format phone number to international format.
    
    Args:
        phone: Phone number in various formats
        
    Returns:
        Formatted phone number (254XXXXXXXXX)
        
    Raises:
        ValueError: If phone number is invalid
    """
    # Remove any non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Handle different formats
    if digits.startswith('0'):
        digits = '254' + digits[1:]
    elif digits.startswith('254'):
        pass  # Already correct format
    elif digits.startswith('7'):
        digits = '254' + digits
    elif digits.startswith('1'):
        digits = '254' + digits
    else:
        raise ValueError(f"Invalid phone number format: {phone}")
    
    # Check length
    if len(digits) != 12:
        raise ValueError(f"Phone number must be 12 digits: {digits}")
    
    return digits


def validate_amount(amount: float, min_amount: float = 1, max_amount: float = 150000) -> float:
    """
    Validate transaction amount.
    
    Args:
        amount: Amount to validate
        min_amount: Minimum allowed amount
        max_amount: Maximum allowed amount
        
    Returns:
        Validated amount
        
    Raises:
        ValueError: If amount is invalid
    """
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")
    
    if amount < min_amount:
        raise ValueError(f"Amount must be at least {min_amount}")
    
    if amount > max_amount:
        raise ValueError(f"Amount cannot exceed {max_amount}")
    
    # Round to 2 decimal places
    return round(amount, 2)