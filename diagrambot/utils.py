"""
Utility functions for diagrambot.
"""

import os
from pathlib import Path


def ensure_openai_api_key():
    """
    Ensure OPENAI_API_KEY is available in the environment.
    
    Checks for OPENAI_API_KEY environment variable and attempts to load it
    from .env files if not found.
    
    Returns:
        bool: True if API key is available
        
    Raises:
        ValueError: If API key cannot be found
    """
    if os.getenv("OPENAI_API_KEY"):
        return True
    
    # Try to load from .env file
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            if os.getenv("OPENAI_API_KEY"):
                print("Loaded OPENAI_API_KEY from .env file")
                return True
        except ImportError:
            pass
    
    # Check for .env in project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            if os.getenv("OPENAI_API_KEY"):
                print("Loaded OPENAI_API_KEY from project .env file")
                return True
        except ImportError:
            pass
    
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. "
        "You can set it with os.environ['OPENAI_API_KEY'] = 'your_api_key' "
        "or by adding it to a .env file."
    )


def build_prompt(prompt_file: str = None) -> str:
    """
    Build prompt for the diagrambot.
    
    Reads the base prompt from the package for diagram generation.
    
    Args:
        prompt_file: Path to prompt file (optional)
        
    Returns:
        str: The complete prompt
    """
    if prompt_file is None:
        prompt_file = Path(__file__).parent / "prompts" / "prompt.md"
    
    return Path(prompt_file).read_text()
