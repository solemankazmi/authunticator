import os
import sys
from datasette.cli import cli
from click.testing import CliRunner

# Database file name
DB_FILE = 'users.db'

def run_datasette():
    if not os.path.exists(DB_FILE):
        print(f"Error: '{DB_FILE}' not found in the current directory.")
        return

    print(f"Using existing database: '{DB_FILE}'")
    print("Starting Datasette...")
    print("Once running, visit http://localhost:9007 in your web browser.")
    
    runner = CliRunner()
    result = runner.invoke(cli, [DB_FILE, "--port", "9007", "--host", "0.0.0.0"])
    
    if result.exit_code != 0:
        print("An error occurred while running Datasette:")
        print(result.output)
        sys.exit(1)

if __name__ == "__main__":
    run_datasette()
