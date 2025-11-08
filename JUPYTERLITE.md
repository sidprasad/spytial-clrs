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

3. **fix_jupyterlite_paths.py**: Post-processing script that:
   - Converts absolute paths to relative paths in JupyterLite config files
   - Enables deployment in subdirectories (e.g., /spytial-clrs/)
   - Allows anonymous deployment (e.g., via anonymous.4open.science)

4. **create_lab_redirect.py**: Post-processing script that:
   - Replaces the root index.html with a redirect to /lab
   - Ensures users land directly in the JupyterLab interface
   - Only the lab interface is exposed (no README or other interfaces)

5. **.github/workflows/deploy.yml**: GitHub Actions workflow that:
   - Builds the JupyterLite site
   - Fixes paths for subdirectory deployment
   - Creates redirect to lab interface
   - Deploys to GitHub Pages

## How it Works

1. On push to main or manual workflow dispatch, GitHub Actions:
   - Checks out the repository
   - Installs jupyterlite-core and jupyterlite-pyodide-kernel
   - Builds the static JupyterLite site with notebooks
   - Runs the path fixing script to convert absolute paths to relative paths
   - Creates a redirect from root to /lab (only lab interface matters)
   - Deploys to GitHub Pages

2. When users visit the site:
   - The browser downloads the JupyterLite app
   - Pyodide (Python in WebAssembly) loads in the browser
   - Users can run Python code entirely client-side
   - Packages are installed from PyPI via piplite when needed

## Path Handling

By default, JupyterLite generates configuration files with absolute paths (e.g., `/lab`), which breaks when deployed to subdirectories. The `fix_jupyterlite_paths.py` script post-processes the generated files to use relative paths (e.g., `./lab`), enabling:

- Anonymous deployment platforms (e.g., anonymous.4open.science)
- Easy redistribution and mirroring of the site

Additionally, `create_lab_redirect.py` replaces the root index.html with a redirect to /lab, ensuring users land directly in the JupyterLab interface (the only interface that matters for this deployment).

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
jupyter lite build --contents src --output-dir dist --config jupyter-lite.json
python fix_jupyterlite_paths.py
python create_lab_redirect.py
jupyter lite serve
```

Then visit http://localhost:8000 (will redirect to /lab)

To test subdirectory deployment locally:
```bash
cd dist
python -m http.server 8000
```
Then visit http://localhost:8000/lab/

## Deployment

The site is automatically deployed to: [REDACTED]

Note: GitHub Pages must be enabled in the repository settings with source set to "GitHub Actions".

### Netlify

The repository is configured for Netlify deployment via the `netlify.toml` file. To deploy to Netlify:

1. **Connect your repository to Netlify:**
   - Go to [Netlify](https://app.netlify.com/)
   - Click "Add new site" > "Import an existing project"
   - Select your Git provider and authorize access
   - Choose the `spytial-clrs` repository

2. **Configure build settings:**
   - Netlify will automatically detect the `netlify.toml` configuration
   - Build command: Defined in `netlify.toml`
   - Publish directory: `_output`
   - No additional configuration needed

3. **Deploy:**
   - Netlify will automatically build and deploy on every push to main
   - The build process will:
     - Install JupyterLite dependencies
     - Build the static JupyterLite site
     - Fix paths for subdirectory deployment
     - Create redirect to the JupyterLab interface

The `netlify.toml` configuration includes:
- Build commands that mirror the GitHub Actions workflow
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- Caching headers for optimal performance
- Proper MIME type for WebAssembly files
