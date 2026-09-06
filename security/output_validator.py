import re 
from typing import Tuple

def validate_output(response:str)-> Tuple[bool,str]:
    """
    Validates that the final LLM response doesn't leak system prompts
    or contain highly toxic patterns before sending to user.
    """
    if "You are security classifier" in response or "You are an AI assistant" in response:
        return False, "System Prompt leakage detected in output"

    if re.search (r"(\bpassword\b|\bsecret_key\b).{0,20}[:=]", response, re.IGNORECASE):
        return False, "Potential credentails leakage detected (jailbroken)"
    
    #Checking for toxic language
    if "kill myself" in response or "suicide" in response:
        return False, "Sensitive Content Detected (Self Harm)"


    return True, "output is Safe."    

    