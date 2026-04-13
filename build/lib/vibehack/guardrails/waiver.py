from vibehack.ui.tui import ask_waiver

def verify_unchained_access(unchained: bool) -> bool:
    """
    If unchained mode is requested, force the user to accept the liability waiver.
    Returns True if safe to proceed, False if aborted.
    """
    if not unchained:
        return True
        
    return ask_waiver()
