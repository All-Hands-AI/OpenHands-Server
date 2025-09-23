"""Main entry point for OpenHands Server."""

import argparse


def main() -> None:
    """Main entry point for the OpenHands Server."""
    parser = argparse.ArgumentParser(
        description="OpenHands Server - REST/WebSocket interface for OpenHands AI Agent"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument("--version", action="version", version="OpenHands Server 0.1.0")

    args = parser.parse_args()

    print(f"OpenHands Server starting on {args.host}:{args.port}")

    import uvicorn

    from .app import app

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
