import random
import string

def generate_api_key_suffix(length: int = 4) -> str:
    """Generate a random API key suffix like 'C1Z5'
    
    Args:
        length: Length of the suffix (default: 4)
    
    Returns:
        A random string with uppercase letters and digits
    """
    # Use uppercase letters and digits for the suffix
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_full_api_key(prefix: str = "EU1CW20nX5oau42xBSgm") -> str:
    """Generate a full API key with the given prefix pattern
    
    Args:
        prefix: The base prefix to use (default uses the pattern from the example)
    
    Returns:
        A full API key string with a random suffix like 'C1Z5'
    """
    # Generate the suffix (last 4 characters like C1Z5)
    suffix = generate_api_key_suffix(4)
    
    # Combine prefix with the generated suffix
    return prefix + suffix

if __name__ == "__main__":
    # Example usage
    print("Generate API key suffix (like C1Z5):")
    for i in range(5):
        suffix = generate_api_key_suffix()
        print(f"  {suffix}")
    
    print("\nGenerate full API key with prefix:")
    for i in range(5):
        api_key = generate_full_api_key()
        print(f"  {api_key}")
    
    print("\nGenerate with custom prefix:")
    custom_prefix = "EU1CW20nX5oau42xBSgm"
    for i in range(3):
        api_key = generate_full_api_key(custom_prefix)
        print(f"  {api_key}")