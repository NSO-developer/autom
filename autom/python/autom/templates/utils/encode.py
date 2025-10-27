#!/usr/bin/env python3
"""
Script to generate a Base64-encoded Basic Authentication token.
The script prompts for username and password after execution.
Usage: python3 encode_auth.py
"""

import base64
import getpass
import sys
import os


def generate_basic_auth_token(username: str, password: str) -> str:
    """
    Encodes a username and password into a Base64 string for Basic Authentication.
    :param username: NSO username.
    :param password: NSO password.
    :return: token
    """
    if not username or not password:
        raise ValueError("Both username and password must be provided and cannot be empty.")
    
    credentials = f"{username}:{password}"
    credentials_bytes = credentials.encode('utf-8')
    base64_bytes = base64.b64encode(credentials_bytes)
    base64_string = base64_bytes.decode('utf-8')
    return base64_string


def create_export_script(token: str) -> str:
    """
    Creates a shell script file to export the NSO_AUTH_TOKEN environment variable.
    :param token: The Base64-encoded authentication token.
    :return: The filename of the created script.
    """
    
    filename = "set_nso_token.sh"
    content = f"#!/bin/bash\nexport NSO_AUTH_TOKEN=\"{token}\"\necho \"NSO_AUTH_TOKEN environment variable has been set.\"\n"
    
    try:
        with open(filename, 'w') as f:
            f.write(content)
            os.chmod(filename, 0o755)
        
        return filename
    except IOError as e:
        raise IOError(f"Failed to create export script: {e}")

def execute_env_var_generator():
    print(f"\n============================================================\
          \nThis script will prompt you for a username and password,\
          \nthen generate a Base64-encoded authentication token.\
          \n============================================================\n")
    
    try:
        username = input("Enter username: ").strip()
        
        if not username:
            print("\nError: Username cannot be empty.", file=sys.stderr)
            sys.exit(1)
        password = getpass.getpass(f"Enter password for user '{username}': ")
        
        if not password:
            print("\nError: Password cannot be empty.", file=sys.stderr)
            sys.exit(1)
        
        token = generate_basic_auth_token(username, password)
        script_filename = create_export_script(token)
        
        print(f"\n============================================================\
              \n\n--- Encoded Token (Base64) ---\
              \n\n{token}\
              \n\n\n--- Environment Variable Script Created ---\
              \n\nFile: {script_filename}\
              \n\n\n--- To Set the Environment Variable ---\
                \n\nRun this command in your terminal:   source {script_filename}")
        
        print("\n" + "=" * 60 + "\n")
    except (EOFError, KeyboardInterrupt):
        print("\n\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    execute_env_var_generator()
