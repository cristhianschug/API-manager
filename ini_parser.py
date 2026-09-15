"""Parser for confrede.ini files (Firebird connection config)"""
import configparser
from typing import Dict, Any
from io import StringIO

def parse_confrede_ini(file_content: bytes) -> Dict[str, Any]:
    """
    Parse confrede.ini content and extract Firebird connection credentials.

    Expected format:
        [Acesso]
        UserName=...
        Password=...
        Server=...
        Port=...
        DataBase=...
        Protocol=...
        CaminhoBackup=...

    Args:
        file_content: raw bytes from uploaded .ini file

    Returns:
        dict with keys: username, password, server, port, database, protocol (ignored), backup_path (ignored)

    Raises:
        ValueError: if parsing fails or required fields missing
    """
    try:
        # Decode bytes to string (try UTF-8, fall back to Latin-1)
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            text = file_content.decode('latin-1')

        config = configparser.ConfigParser()
        config.read_string(text)

        if 'Acesso' not in config:
            raise ValueError("confrede.ini must have [Acesso] section")

        section = config['Acesso']
        required_keys = ['UserName', 'Password', 'Server', 'Port', 'DataBase']
        missing = [k for k in required_keys if k not in section]
        if missing:
            raise ValueError(f"Missing required fields in [Acesso]: {', '.join(missing)}")

        return {
            'username': section['UserName'].strip(),
            'password': section['Password'].strip(),
            'server': section['Server'].strip(),
            'port': int(section['Port'].strip()),
            'database': section['DataBase'].strip(),
            'protocol': section.get('Protocol', '0').strip(),  # usually '0' for TCP
            'backup_path': section.get('CaminhoBackup', '').strip(),
        }

    except configparser.Error as e:
        raise ValueError(f"Failed to parse confrede.ini: {e}")
    except ValueError as e:
        raise ValueError(f"Invalid confrede.ini format: {e}")
    except Exception as e:
        raise ValueError(f"Error parsing confrede.ini: {type(e).__name__}: {e}")
