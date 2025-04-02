import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging

from .api.endpoints import router as api_router
from .api.civitai_endpoints import router as civitai_router
from .core.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI(
    title="Civitai Browser",
    description="Standalone application for downloading models from Civitai",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Set up templates
templates_path = Path(__file__).parent.parent / "static" / "templates"
templates = Jinja2Templates(directory=templates_path)

# Include API routes
app.include_router(api_router, prefix="/api")

# Include Civitai specific routes
app.include_router(civitai_router)

# Don't automatically ensure model directories for testing
# Settings().ensure_model_dirs()


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Root endpoint, serves the main HTML page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon"""
    favicon_path = static_path / "favicon.ico"
    if not favicon_path.exists():
        # Create a default empty favicon to avoid 500 errors
        with open(favicon_path, "wb") as f:
            # Minimal valid .ico file
            f.write(
                b"\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x08\x00h\x05\x00\x00\x16\x00\x00\x00(\x00\x00\x00\x10\x00\x00\x00 \x00\x00\x00\x01\x00\x08\x00\x00\x00\x00\x00@\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )
    return FileResponse(favicon_path)


def run_app():
    """Run the application when directly executed"""
    # Get port from environment variable, default to 8000
    port = int(os.environ.get("PORT", 8000))

    # Ensure model directories exist when running the app
    try:
        Settings().ensure_model_dirs()
    except Exception as e:
        # Log but don't crash if we can't create directories
        print(f"Warning: Could not create model directories: {e}")
        print("The application will continue, but downloads may fail.")

    # Start the server
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run_app()
