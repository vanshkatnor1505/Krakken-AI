import os
import sys
import traceback


def setup_paths():
    """Add Backend, Frontend, and current directories to Python path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(current_dir, "Backend")
    frontend_dir = os.path.join(current_dir, "Frontend")

    for path in (backend_dir, frontend_dir, current_dir):
        if path not in sys.path:
            sys.path.append(path)

    print(f"Current directory: {current_dir}")
    print(f"Backend directory: {backend_dir}")
    print(f"Python paths updated.")


def check_imports():
    """Verify all critical Backend and Frontend modules import successfully."""
    print("Checking required module imports...\n")

    backend_modules = [
        'Model', 'Chatbot', 'RealtimeSearchEngine',
        'SpeechToText', 'TextToSpeech', 'Automation'
    ]

    all_imports_ok = True

    for module in backend_modules:
        try:
            __import__(module)
            print(f"✓ Backend.{module}")
        except ImportError as e:
            print(f"✗ Backend.{module}: {e}")
            all_imports_ok = False

    try:
        __import__('GUI')
        print("✓ Frontend.GUI")
    except ImportError as e:
        print(f"✗ Frontend.GUI: {e}")
        all_imports_ok = False

    return all_imports_ok


def create_required_directories():
    """Ensure essential directories exist."""
    directories = [
        "Frontend/Graphics",
        "Frontend/Files",
        "Data",
        "Backend"
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Directory exists or created: {directory}")


def main():
    print("🚀 Starting AI Assistant")
    print("=" * 50)

    setup_paths()
    create_required_directories()

    if not check_imports():
        print("\n❌ Import check failed! Please install missing modules or check your setup.")
        input("Press Enter to exit...")
        return

    try:
        print("\n🎯 Launching GUI...")
        from Frontend.GUI import GraphicalUserInterface
        GraphicalUserInterface()
    except Exception as e:
        print(f"❌ Error during GUI launch: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
