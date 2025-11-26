"""
Work-Ink Offer SDK wrapper for monetization.
Shows an optional Opera browser offer to users before installation.
"""
import ctypes
import os
import sys
import logging

# Publisher ID for Ascendara
PUBLISHER_ID = os.getenv('PUBLISHER_ID')

# Return codes from the SDK
class OfferResult:
    INSTALLER_LAUNCHED = 1   # User accepted, installer launched
    BROWSER_OPENED = 0       # User accepted, browser opened
    USER_DECLINED = -1       # User declined the offer
    WINDOW_CLOSED = -2       # User closed the offer window
    API_ERROR = -3           # Network issue or no offers available


def get_sdk_path():
    """Get the path to the SDK DLL."""
    # When running as PyInstaller bundle, files are extracted to _MEIPASS
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
        dll_path = os.path.join(base_dir, 'core', 'work-ink-offer-sdk.dll')
    else:
        # Development mode - look in same directory as this module
        module_dir = os.path.dirname(os.path.abspath(__file__))
        dll_path = os.path.join(module_dir, 'work-ink-offer-sdk.dll')
    
    return dll_path


def show_offer():
    """
    Show the Work-Ink offer to the user.
    
    Returns:
        int: Result code from OfferResult class
        - 1: Installer launched (user accepted)
        - 0: Browser opened (user accepted)
        - -1: User declined
        - -2: User closed window
        - -3: API error or SDK not available
    """
    dll_path = get_sdk_path()
    
    if not os.path.exists(dll_path):
        logging.warning(f"Work-Ink SDK not found at {dll_path}, skipping offer")
        return OfferResult.API_ERROR
    
    try:
        # Load the SDK DLL
        sdk = ctypes.CDLL(dll_path)
        
        # Configure function signature
        sdk.runOffer.argtypes = [ctypes.c_int]
        sdk.runOffer.restype = ctypes.c_int
        
        # Call the offer function
        logging.info(f"Showing Work-Ink offer (Publisher ID: {PUBLISHER_ID})")
        result = sdk.runOffer(PUBLISHER_ID)
        
        # Log the result
        if result == OfferResult.INSTALLER_LAUNCHED:
            logging.info("Offer result: User accepted - installer launched")
        elif result == OfferResult.BROWSER_OPENED:
            logging.info("Offer result: User accepted - browser opened")
        elif result == OfferResult.USER_DECLINED:
            logging.info("Offer result: User declined")
        elif result == OfferResult.WINDOW_CLOSED:
            logging.info("Offer result: User closed window")
        elif result == OfferResult.API_ERROR:
            logging.warning("Offer result: API error or no offers available")
        else:
            logging.warning(f"Offer result: Unknown code {result}")
        
        return result
        
    except OSError as e:
        logging.error(f"Failed to load Work-Ink SDK: {e}")
        return OfferResult.API_ERROR
    except Exception as e:
        logging.error(f"Error showing offer: {e}")
        return OfferResult.API_ERROR
