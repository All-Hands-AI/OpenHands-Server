import argparse

import uvicorn


def main(app_name: str = "openhands_server.local_server.local_api:api"):
    parser = argparse.ArgumentParser(description="Run the OpenHands Local FastAPI app")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload", default=True, action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    print(f"🚀 Starting OpenHands Local app on {args.host}:{args.port}")
    print(f"📖 API docs will be available at http://{args.host}:{args.port}/docs")
    print(f"🔄 Auto-reload: {'enabled' if args.reload else 'disabled'}")
    print()

    uvicorn.run(app_name, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
