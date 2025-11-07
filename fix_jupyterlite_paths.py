#!/usr/bin/env python3
"""
Post-process JupyterLite build output to make paths relative.
This allows the site to be deployed in any subdirectory or domain.
"""
import json
from pathlib import Path


def fix_appurl_in_json(json_path: Path) -> None:
    """Fix absolute appUrl paths in jupyter-lite.json files.
    
    Args:
        json_path: Path to the jupyter-lite.json file to fix
        
    Raises:
        json.JSONDecodeError: If the file contains invalid JSON
        OSError: If file operations fail
    """
    if not json_path.exists():
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check if jupyter-config-data exists and has appUrl
    if 'jupyter-config-data' in data:
        config = data['jupyter-config-data']
        if 'appUrl' in config and config['appUrl'].startswith('/'):
            # Convert absolute path to relative path
            # For /lab -> ./lab, for /tree -> ./tree, etc.
            old_url = config['appUrl']
            new_url = '.' + old_url
            config['appUrl'] = new_url
            print(f"Fixed {json_path}: {old_url} -> {new_url}")
            
            # Write back the modified JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)


def main() -> int:
    """Fix all jupyter-lite.json files in the dist directory.
    
    Returns:
        0 on success, 1 on error
    """
    dist_dir = Path('dist')
    
    if not dist_dir.exists():
        print("Error: dist directory not found. Please run 'jupyter lite build' first.")
        return 1
    
    # Find all jupyter-lite.json files
    json_files = list(dist_dir.rglob('jupyter-lite.json'))
    
    print(f"Found {len(json_files)} jupyter-lite.json files")
    
    for json_file in json_files:
        fix_appurl_in_json(json_file)
    
    print("Path fixing complete!")
    return 0


if __name__ == '__main__':
    exit(main())
