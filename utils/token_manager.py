from typing import Optional, Dict
import keyring
from keyring.errors import KeyringLocked, NoKeyringError
import traceback
import base64
import pathlib
from binascii import Error as Base64Error
from logger import Logger
from errors import InvalidLoginTokenError

logger = Logger(__name__)

SERVICE_NAME = "mwm.datallog.com"  # Replace with your service name
TOKEN_USER_IDENTIFIER = "sdk"  # Or could be an actual username


def test_keyring() -> bool:
    """
    Tests if the keyring is available and can be used.
    Returns:
        bool: True if keyring is available, False otherwise.
    """
    try:
        keyring.set_password(SERVICE_NAME, TOKEN_USER_IDENTIFIER, "test_token")
        token = keyring.get_password(SERVICE_NAME, TOKEN_USER_IDENTIFIER)
        if token != "test_token":
            logger.warning(
                "Warning: Keyring is not functioning as expected. Saving token as cleartext."
            )
            return False
        return True
    except NoKeyringError:
        logger.info("No keyring backend found. Saving token as cleartext.")
        return False
    except Exception:
        logger.info(
            f"An error occurred while testing the keyring. Saving token as cleartext"
        )
        return False


def safe_save_token(token: str) -> None:
    """
    Saves a token to the system's keyring.
    Args:
        service_name (str): The name of the service the token is for.
        username (str): The username or identifier associated with the token.
        token (str): The token to save.
    """
    try:
        keyring.set_password(SERVICE_NAME, TOKEN_USER_IDENTIFIER, token)
        logger.info(
            f"Token saved successfully for {TOKEN_USER_IDENTIFIER} in {SERVICE_NAME}, {token[:10]}... (truncated for security)"
        )
    except NoKeyringError:
        logger.info("No keyring backend found.")
    except Exception:
        logger.info(f"An error occurred while saving the token.")
        logger.info(traceback.format_exc())


def safe_retrieve_token() -> Optional[Dict[str, str]]:
    """
    Retrieves a token from the system's keyring.
    Args:
        service_name (str): The name of the service the token is for.
        username (str): The username or identifier associated with the token.
    Returns:
        str or None: The retrieved token, or None if not found or an error occurs.
    """
    try:
        token = keyring.get_password(SERVICE_NAME, TOKEN_USER_IDENTIFIER)

        if token:
            return decode_token(token)
        else:
            return None
    except (NoKeyringError, KeyringLocked):
        logger.info("No keyring backend found. Please install a keyring backend.")
        return None
    except Exception:
        logger.info(f"An error occurred while retrieving the token")
        logger.info(traceback.format_exc())
        return None


def safe_delete_token() -> None:
    """
    Deletes a token from the system's keyring.
    Args:
        service_name (str): The name of the service the token is for.
        username (str): The username or identifier associated with the token.
    """
    try:
        # First, check if the password exists before trying to delete
        if keyring.get_password(SERVICE_NAME, TOKEN_USER_IDENTIFIER) is not None:
            keyring.delete_password(SERVICE_NAME, TOKEN_USER_IDENTIFIER)

    except NoKeyringError:
        logger.info("No keyring backend found.")
    except Exception:
        logger.info(f"An error occurred while deleting the token")
        logger.info(traceback.format_exc())


import hashlib

def get_project_id(project_path: pathlib.Path) -> str:
    """
    Generates a unique ID for a project based on its absolute path.
    """
    return hashlib.md5(str(project_path.absolute()).encode()).hexdigest()


def unsafe_token_file(project_id: Optional[str] = None) -> pathlib.Path:
    if project_id:
        return pathlib.Path(__file__).parent.parent / "projects" / project_id / ".credentials"
    return pathlib.Path(__file__).parent.parent / ".credentials"


def unsafe_user_file(project_id: Optional[str] = None) -> pathlib.Path:
    if project_id:
        return pathlib.Path(__file__).parent.parent / "projects" / project_id / ".user"
    return pathlib.Path(__file__).parent.parent / ".user"


def safe_save_token(token: str, project_id: Optional[str] = None) -> None:
    """
    Saves a token to the system's keyring.
    """
    try:
        identifier = TOKEN_USER_IDENTIFIER
        if project_id:
            identifier += f"_{project_id}"
        keyring.set_password(SERVICE_NAME, identifier, token)
    except NoKeyringError:
        logger.info("No keyring backend found.")


def safe_retrieve_token(project_id: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Retrieves a token from the system's keyring.
    """
    try:
        identifier = TOKEN_USER_IDENTIFIER
        if project_id:
            identifier += f"_{project_id}"
        token = keyring.get_password(SERVICE_NAME, identifier)
        if token:
            return decode_token(token)
        return None
    except (NoKeyringError, KeyringLocked):
        logger.info("No keyring backend found.")
        return None


def unsafe_save_token(token: str, project_id: Optional[str] = None) -> None:
    """
    Saves a token to a file.
    """
    try:
        target_file = unsafe_token_file(project_id)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w") as f:
            f.write(token)
    except Exception as e:
        print(f"An error occurred while saving the token: {e}")


def unsafe_retrieve_token(project_id: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Retrieves a token from a file.
    """
    try:
        target_file = unsafe_token_file(project_id)
        if target_file.exists() is False:
            return None

        with open(target_file, "r") as f:
            token = f.read().strip()
        if token:
            return decode_token(token)
        else:
            return None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"An error occurred while retrieving the token: {e}")
        return None


def save_user_info(info: Dict[str, str], project_path: Optional[pathlib.Path] = None) -> None:
    """
    Saves user info to a file.
    """
    try:
        project_id = get_project_id(project_path) if project_path else None
        user_file = unsafe_user_file(project_id)
        user_file.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(user_file, "w") as f:
            json.dump(info, f)
    except Exception as e:
        logger.error(f"Error saving user info: {e}")


def retrieve_user_info(project_path: Optional[pathlib.Path] = None) -> Optional[Dict[str, str]]:
    """
    Retrieves user info from a file.
    """
    try:
        project_id = get_project_id(project_path) if project_path else None
        target_file = unsafe_user_file(project_id)
        
        # Fallback to global if local not found
        if project_id and not target_file.exists():
            target_file = unsafe_user_file(None)

        if not target_file.exists():
            return None
        import json
        with open(target_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error retrieving user info: {e}")
        return None


def delete_user_info(project_path: Optional[pathlib.Path] = None) -> None:
    """
    Deletes the user info file.
    """
    try:
        project_id = get_project_id(project_path) if project_path else None
        user_file = unsafe_user_file(project_id)
        if user_file.exists():
            user_file.unlink()
    except Exception as e:
        logger.error(f"Error deleting user info: {e}")


def save_token(encoded_token: str, project_path: Optional[pathlib.Path] = None) -> None:
    """
    Saves the tokens.
    """
    project_id = get_project_id(project_path) if project_path else None
    
    if test_keyring():
        safe_save_token(encoded_token, project_id)
    else:
        unsafe_save_token(encoded_token, project_id)


def retrieve_token(project_path: Optional[pathlib.Path] = None) -> Optional[Dict[str, str]]:
    """
    Retrieves the tokens.
    """
    project_id = get_project_id(project_path) if project_path else None
    
    def try_decode(encoded_str: Optional[str]) -> Optional[Dict[str, str]]:
        if not encoded_str:
            return None
        try:
            return decode_token(encoded_str)
        except InvalidLoginTokenError:
            return None

    # Try project-specific token
    token = None
    if project_id:
        token = try_decode(safe_retrieve_password(project_id))
        if token is None:
            token = try_decode(unsafe_retrieve_password_str(project_id))
    
    # Fallback to global token
    if token is None:
        token = try_decode(safe_retrieve_password(None))
        if token is None:
            token = try_decode(unsafe_retrieve_password_str(None))
            
    return token


def safe_retrieve_password(project_id: Optional[str] = None) -> Optional[str]:
    try:
        identifier = TOKEN_USER_IDENTIFIER
        if project_id:
            identifier += f"_{project_id}"
        return keyring.get_password(SERVICE_NAME, identifier)
    except (NoKeyringError, KeyringLocked):
        return None


def unsafe_retrieve_password_str(project_id: Optional[str] = None) -> Optional[str]:
    try:
        target_file = unsafe_token_file(project_id)
        if target_file.exists():
            with open(target_file, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def delete_token(project_path: Optional[pathlib.Path] = None):
    """
    Deletes the tokens.
    """
    project_id = get_project_id(project_path) if project_path else None
    # Keyring doesn't easily support namespaced delete in this helper yet 
    # but we can implement it as:
    try:
        identifier = TOKEN_USER_IDENTIFIER
        if project_id:
            identifier += f"_{project_id}"
        if keyring.get_password(SERVICE_NAME, identifier) is not None:
            keyring.delete_password(SERVICE_NAME, identifier)
    except Exception:
        pass

    unsafe_token_file(project_id).unlink(missing_ok=True)
    delete_user_info(project_path)


def encode_token(authorization: str, x_api_key: str) -> str:
    """
    Encodes the authorization and x-api-key into a base64 string.
    Args:
        authorization (str): The authorization token.
        x_api_key (str): The API key.
    Returns:
        str: The base64 encoded string of the JSON object containing the tokens.
    """
    authorization_token = (
        authorization.split(" ")[1] if " " in authorization else authorization
    )
    token_int = int(authorization_token, 16).to_bytes(20, "big")
    
    x_api_key_bytes = base64.b64decode(x_api_key.encode())

    return base64.b64encode(token_int + x_api_key_bytes).decode()


def decode_token(encoded_token: str) -> Dict[str, str]:
    """
    Decodes a base64 encoded token string into its original JSON format.
    Args:
        encoded_token (str): The base64 encoded token string.
    """
    try:
        decoded_bytes = base64.b64decode(encoded_token)
        token_length = 20
        if len(decoded_bytes) != 50:
            raise InvalidLoginTokenError("Invalid token. Please check your token.")

        data = {
            "Authorization": "Token " + decoded_bytes[:token_length].hex().lower(),
            "x-api-key": base64.b64encode(decoded_bytes[token_length:]).decode(),
        }
        return data
    except (ValueError, Base64Error) as e:
        raise InvalidLoginTokenError(f"Invalid token. Please check your token.") from e
