"""
7000%AUTO - AI Automation System
Main Entry Point

This module initializes the FastAPI application, database, and orchestrator.
It handles graceful startup and shutdown of all system components.

Features:
- Database initialization on startup
- FastAPI web server with uvicorn
- Orchestrator workflow running in background task
- Graceful shutdown handling
- Structured logging with configurable log level
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import project modules
from config import settings
from database import init_db, close_db
from orchestrator import WorkflowOrchestrator


# =============================================================================
# Logging Configuration
# =============================================================================

def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging with the specified log level.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Set root logger level
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
        stream=sys.stdout,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not settings.DEBUG else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize logging
configure_logging(settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


# =============================================================================
# Global State
# =============================================================================

# Global orchestrator instance
orchestrator: Optional[WorkflowOrchestrator] = None

# Background task reference
orchestrator_task: Optional[asyncio.Task] = None

# Shutdown event for graceful termination
shutdown_event = asyncio.Event()


# =============================================================================
# Orchestrator Management
# =============================================================================

async def run_orchestrator_loop() -> None:
    """
    Run the orchestrator pipeline in a continuous loop.
    
    The orchestrator will run the full pipeline and then wait for a configured
    interval before starting the next run. This loop continues until shutdown
    is requested.
    """
    global orchestrator
    
    orchestrator = WorkflowOrchestrator()
    
    logger.info(
        "Orchestrator loop started",
        auto_start=settings.AUTO_START,
        max_concurrent_projects=settings.MAX_CONCURRENT_PROJECTS,
    )
    
    while not shutdown_event.is_set():
        try:
            logger.info("Starting orchestrator pipeline run")
            
            # Run the full pipeline
            result = await orchestrator.run_full_pipeline()
            
            if result.get("success"):
                logger.info(
                    "Pipeline completed successfully",
                    project_id=result.get("project_id"),
                    github_url=result.get("github_url"),
                    x_post_url=result.get("x_post_url"),
                    iterations=result.get("dev_test_iterations"),
                )
            else:
                logger.warning(
                    "Pipeline completed with errors",
                    project_id=result.get("project_id"),
                    error=result.get("error"),
                )
            
            # Wait before next run (or until shutdown)
            # Use a reasonable interval between pipeline runs
            pipeline_interval = 60  # seconds between pipeline runs
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=pipeline_interval
                )
                # If we get here, shutdown was requested
                break
            except asyncio.TimeoutError:
                # Timeout means we should continue the loop
                continue
                
        except asyncio.CancelledError:
            logger.info("Orchestrator loop cancelled")
            break
        except Exception as e:
            logger.error(
                "Orchestrator pipeline error",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Wait before retrying after error
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=30)
                break
            except asyncio.TimeoutError:
                continue
    
    logger.info("Orchestrator loop stopped")


async def stop_orchestrator() -> None:
    """
    Stop the orchestrator gracefully.
    """
    global orchestrator, orchestrator_task
    
    logger.info("Stopping orchestrator...")
    
    # Signal shutdown
    shutdown_event.set()
    
    # Stop the orchestrator if running
    if orchestrator is not None:
        await orchestrator.stop()
    
    # Cancel and wait for background task
    if orchestrator_task is not None and not orchestrator_task.done():
        orchestrator_task.cancel()
        try:
            await asyncio.wait_for(orchestrator_task, timeout=10.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    
    logger.info("Orchestrator stopped")


# =============================================================================
# Database Initialization
# =============================================================================

async def initialize_database() -> None:
    """
    Initialize the database and create all tables.
    """
    logger.info("Initializing database...")
    
    # Ensure required directories exist
    settings.ensure_directories()
    
    # Initialize database tables
    await init_db()
    
    logger.info(
        "Database initialized successfully",
        database_url=settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local",
    )


async def shutdown_database() -> None:
    """
    Close database connections gracefully.
    """
    logger.info("Closing database connections...")
    await close_db()
    logger.info("Database connections closed")


# =============================================================================
# FastAPI Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Handles startup and shutdown events for the FastAPI application:
    - Startup: Initialize database, start orchestrator (if AUTO_START)
    - Shutdown: Stop orchestrator, close database connections
    """
    global orchestrator_task
    
    # === STARTUP ===
    logger.info(
        "Starting 7000%AUTO application",
        app_name=settings.APP_NAME,
        debug=settings.DEBUG,
        host=settings.HOST,
        port=settings.PORT,
    )
    
    try:
        # Initialize database
        await initialize_database()
        
        # Start orchestrator in background if AUTO_START is enabled
        if settings.AUTO_START:
            logger.info("AUTO_START enabled, starting orchestrator background task")
            orchestrator_task = asyncio.create_task(
                run_orchestrator_loop(),
                name="orchestrator-loop"
            )
        else:
            logger.info("AUTO_START disabled, orchestrator will not start automatically")
        
        logger.info(
            "Application startup complete",
            auto_start=settings.AUTO_START,
            github_configured=settings.is_github_configured,
            x_configured=settings.is_x_configured,
            minimax_configured=settings.is_minimax_configured,
        )
        
        yield
        
    finally:
        # === SHUTDOWN ===
        logger.info("Shutting down application...")
        
        # Stop orchestrator
        await stop_orchestrator()
        
        # Close database connections
        await shutdown_database()
        
        logger.info("Application shutdown complete")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous AI System with 6 Orchestrated Agents: Ideator -> Planner -> Developer <-> Tester -> Uploader -> Evangelist",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Core API Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with application info."""
    return {
        "name": settings.APP_NAME,
        "description": "Autonomous AI System with 6 Orchestrated Agents",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs" if settings.DEBUG else None,
        },
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    """
    orchestrator_status = "running" if (orchestrator and orchestrator.is_running) else "idle"
    if not settings.AUTO_START and orchestrator is None:
        orchestrator_status = "disabled"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "healthy",
            "orchestrator": orchestrator_status,
        },
        "config": {
            "auto_start": settings.AUTO_START,
            "debug": settings.DEBUG,
            "github_configured": settings.is_github_configured,
            "x_configured": settings.is_x_configured,
            "minimax_configured": settings.is_minimax_configured,
        }
    }


@app.get("/status")
async def get_status():
    """
    Get detailed system status.
    """
    return {
        "app_name": settings.APP_NAME,
        "orchestrator": {
            "running": orchestrator.is_running if orchestrator else False,
            "auto_start": settings.AUTO_START,
        },
        "configuration": {
            "host": settings.HOST,
            "port": settings.PORT,
            "debug": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
            "workspace_dir": str(settings.WORKSPACE_DIR),
            "max_concurrent_projects": settings.MAX_CONCURRENT_PROJECTS,
        },
        "integrations": {
            "github": settings.is_github_configured,
            "x_twitter": settings.is_x_configured,
            "minimax": settings.is_minimax_configured,
        },
    }


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else None,
        }
    )


# =============================================================================
# Signal Handlers
# =============================================================================

def create_signal_handler():
    """
    Create signal handlers for graceful shutdown.
    """
    def handle_signal(signum, frame):
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        shutdown_event.set()
    
    return handle_signal


def setup_signal_handlers():
    """
    Set up signal handlers for SIGTERM and SIGINT.
    """
    handler = create_signal_handler()
    
    # Register signal handlers (Unix only)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)
    else:
        # Windows: only SIGINT (Ctrl+C) is supported
        signal.signal(signal.SIGINT, handler)


# =============================================================================
# Mount Web Dashboard (if available)
# =============================================================================

try:
    from web.app import dashboard_app
    app.mount("/dashboard", dashboard_app)
    logger.info("Web dashboard mounted at /dashboard")
except ImportError:
    logger.warning("Web dashboard not available, skipping mount")
except Exception as e:
    logger.warning(f"Failed to mount web dashboard: {e}")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """
    Main entry point for running the application.
    
    Configures and starts the uvicorn server with the FastAPI application.
    """
    # Set up signal handlers
    setup_signal_handlers()
    
    logger.info(
        "Starting uvicorn server",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.DEBUG,
    )
    
    # Run uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        # Production settings
        workers=1,  # Use 1 worker for orchestrator state consistency
        loop="auto",
        http="auto",
        # Timeouts
        timeout_keep_alive=30,
    )


if __name__ == "__main__":
    main()
