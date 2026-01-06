#!/usr/bin/env python3
"""
Quick setup script for StreamWeaver development
"""
import subprocess
import sys


def run_command(cmd, description):
    """Run a command and report the result"""
    print(f"\n{'=' * 60}")
    print(f"📦 {description}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Failed to {description}")
        return False
    print(f"✅ {description} completed")
    return True


def main():
    print("\n🚀 StreamWeaver Development Setup")
    print("=" * 60)
    
    commands = [
        ("python -m pip install --upgrade pip", "Upgrading pip"),
        ("pip install -e '.[dev]'", "Installing StreamWeaver in dev mode"),
    ]
    
    success = True
    for cmd, description in commands:
        if not run_command(cmd, description):
            success = False
            break
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Setup completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run tests: pytest")
        print("  2. Run examples: python examples/basic/simple_agent.py")
        print("  3. Read docs: open README.md")
        print("\nHappy streaming! 🎉\n")
        return 0
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
