#!/usr/bin/env python3
"""Test runner script for different test categories."""

import subprocess
import sys
import argparse


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
        return True
    else:
        print(f"❌ {description} - FAILED")
        return False


def main():
    parser = argparse.ArgumentParser(description='Run LINE Chatbot tests')
    parser.add_argument('--category', choices=['unit', 'component', 'smoke', 'all'], 
                       default='all', help='Test category to run')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage')
    
    args = parser.parse_args()
    
    results = []
    
    if args.category in ['unit', 'all']:
        cmd = "python -m pytest tests/unit/ -v"
        if args.coverage:
            cmd += " --cov=src --cov-report=term-missing"
        results.append(run_command(cmd, "Unit Tests (Fast, Isolated)"))
    
    if args.category in ['component', 'all']:
        cmd = "python -m pytest tests/component/ -v -m component"
        results.append(run_command(cmd, "Component Tests (Real Dependencies)"))
    
    if args.category in ['smoke', 'all']:
        cmd = "python -m pytest tests/smoke/ -v -m smoke"
        results.append(run_command(cmd, "Smoke Tests (End-to-End)"))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for i, result in enumerate(results):
        test_type = ['Unit', 'Component', 'Smoke'][i] if args.category == 'all' else args.category.title()
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_type} Tests: {status}")
    
    total_passed = sum(results)
    total_tests = len(results)
    
    print(f"\nOverall: {total_passed}/{total_tests} test suites passed")
    
    if total_passed == total_tests:
        print("🎉 All test suites passed!")
        sys.exit(0)
    else:
        print("⚠️  Some test suites failed")
        sys.exit(1)


if __name__ == "__main__":
    main()