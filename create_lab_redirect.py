#!/usr/bin/env python3
"""
Post-process JupyterLite build output to redirect root to /lab.
This ensures users land directly in JupyterLab interface.
"""
from pathlib import Path


def create_redirect_index() -> None:
    """Create a simple redirect index.html that sends users to /lab.
    
    Operates on dist/index.html specifically.
    
    Raises:
        OSError: If file write operations fail
    """
    redirect_html = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta http-equiv="refresh" content="0; url=./lab/index.html" />
    <title>SpyTial CLRS - Redirecting to JupyterLab...</title>
    <style>
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        margin: 0;
        background-color: #f5f5f5;
      }
      .message {
        text-align: center;
        padding: 20px;
      }
      a {
        color: #2196F3;
        text-decoration: none;
      }
      a:hover {
        text-decoration: underline;
      }
    </style>
  </head>
  <body>
    <div class="message">
      <h1>SpyTial CLRS - Interactive Notebooks</h1>
      <p>Redirecting to JupyterLab...</p>
      <p>If you are not redirected automatically, <a href="./lab/index.html">click here</a>.</p>
    </div>
  </body>
</html>
"""
    
    index_path = Path('dist/index.html')
    if index_path.exists():
        print(f"Replacing {index_path} with redirect to /lab")
        index_path.write_text(redirect_html, encoding='utf-8')
        print("Redirect index.html created successfully")
    else:
        print(f"Warning: {index_path} not found")


def main() -> int:
    """Create redirect index.html.
    
    Returns:
        0 on success, 1 on error
    """
    dist_dir = Path('dist')
    
    if not dist_dir.exists():
        print("Error: dist directory not found. Please run 'jupyter lite build' first.")
        return 1
    
    create_redirect_index()
    return 0


if __name__ == '__main__':
    exit(main())
