# JupyterLite Setup for SpyTial CLRS

This document describes the JupyterLite setup for running the SpyTial CLRS notebooks interactively in the browser.

## Architecture

JupyterLite is a JupyterLab distribution that runs entirely in the browser using WebAssembly and Pyodide (Python compiled to WebAssembly).

## Components

1. **jupyter-lite.json**: Configuration file that specifies:
   - Application name and version
   - Contents to include (notebooks from src/)
   - Package installation URLs for piplite

2. **requirements.txt**: Specifies Python dependencies to be installed via piplite:
   - `spytial-diagramming`: The visualization library used by the notebooks

3. **.github/workflows/deploy.yml**: GitHub Actions workflow that:
   - Builds the JupyterLite site
   - Deploys to GitHub Pages

## How it Works

1. On push to main or manual workflow dispatch, GitHub Actions:
   - Checks out the repository
   - Installs jupyterlite-core and jupyterlite-pyodide-kernel
   - Builds the static JupyterLite site with notebooks
   - Deploys to GitHub Pages

2. When users visit the site:
   - The browser downloads the JupyterLite app
   - Pyodide (Python in WebAssembly) loads in the browser
   - Users can run Python code entirely client-side
   - Packages are installed from PyPI via piplite when needed

## Package Compatibility

**Important**: Not all Python packages work with Pyodide. The package must either:
1. Be a pure Python package (no C extensions), or
2. Have been compiled for WebAssembly/Pyodide

For `spytial-diagramming`:
- If it's pure Python, it should work out of the box
- If it has native dependencies, they need to be available in Pyodide
- Users may need to manually install it in the notebook with: `%pip install spytial-diagramming`

## Testing

To test locally before deploying:
```bash
pip install jupyterlite-core jupyterlite-pyodide-kernel jupyter-server
jupyter lite build --contents src --output-dir dist
jupyter lite serve
```

Then visit http://localhost:8000

## Deployment

The site is automatically deployed to: https://sidprasad.github.io/spytial-clrs/

Note: GitHub Pages must be enabled in the repository settings with source set to "GitHub Actions".
