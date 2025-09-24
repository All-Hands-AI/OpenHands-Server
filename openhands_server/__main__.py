"""Main entry point for OpenHands Server."""

import argparse

import uvicorn

from openhands_server.api import api


def main() -> None:
    """Main entry point for the OpenHands Server."""
    parser = argparse.ArgumentParser(description="OpenHands Enterprise Server APP")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=3000, help="Port to bind to (default: 3000)"
    )
    parser.add_argument(
        "--reload",
        dest="reload",
        default=False,
        action="store_true",
        help="Enable auto-reload (disabled by default)",
    )

    args = parser.parse_args()

    print(f"🚀 Starting OpenHands Enterprise Server on {args.host}:{args.port}")
    print(f"📖 API docs will be available at http://{args.host}:{args.port}/docs")
    print(f"🔄 Auto-reload: {'enabled' if args.reload else 'disabled'}")
    print()

    uvicorn.run(api, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
