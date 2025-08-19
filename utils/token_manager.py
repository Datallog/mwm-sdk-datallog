from typing import Optional, Dict
import keyring
from keyring.errors import NoKeyringError
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
    except NoKeyringError:
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


def unsafe_token_file() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent / ".credentials"


def unsafe_save_token(token: str) -> None:
    """
    Saves a token to a file in the current working directory.
    Args:
        token (str): The token to save.
    """
    try:
        with open(unsafe_token_file(), "w") as f:
            f.write(token)
    except Exception as e:
        print(f"An error occurred while saving the token: {e}")


def unsafe_retrieve_token() -> Optional[Dict[str, str]]:
    """
    Retrieves a token from a file in the current working directory.
    Returns:
        str or None: The retrieved token, or None if not found or an error occurs.
    """
    try:
        if unsafe_token_file().exists() is False:
            return None

        with open(unsafe_token_file(), "r") as f:
            token = f.read().strip()
        if token:
            return decode_token(token)
        else:
            return None
    except FileNotFoundError:
        print("Token file not found.")
        return None
    except Exception as e:
        print(f"An error occurred while retrieving the token: {e}")
        return None


def unsafe_delete_token():
    """
    Deletes a token file from the current working directory.
    """
    try:
        if unsafe_token_file().exists():
            unsafe_token_file().unlink()
            print(f"Token file {unsafe_token_file()} deleted successfully.")
        else:
            print("Token file does not exist.")
    except Exception as e:
        print(f"An error occurred while deleting the token file: {e}")


def save_token(encoded_token: str) -> None:
    """
    Saves the authorization and x-api-key tokens to the system's keyring or a file.
    Args:
        authorization (str): The authorization token.
        x_api_key (str): The API key.
    """
    if test_keyring():
        safe_save_token(encoded_token)
    else:
        unsafe_save_token(encoded_token)


def retrieve_token() -> Optional[Dict[str, str]]:
    """
    Retrieves the authorization and x-api-key tokens from the system's keyring or a file.
    Returns:
        dict: A dictionary containing the authorization and x-api-key tokens.
    """
    token = safe_retrieve_token()
    if token is None:
        token = unsafe_retrieve_token()
    return token


def delete_token():
    """
    Deletes the authorization and x-api-key tokens from the system's keyring or a file.
    """
    safe_delete_token()
    unsafe_delete_token()


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

