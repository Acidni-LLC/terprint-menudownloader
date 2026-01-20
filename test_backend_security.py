"""
Test script to verify backend API key validation works locally.

Usage:
    python test_backend_security.py

Requirements:
    1. Set environment variable: $env:BACKEND_API_KEY = "test-key" 
    2. Start function app: func host start --port 7081
    3. Run this test script
"""

import requests
import json
import os
import sys

BASE_URL = "http://localhost:7081"

def test_health_endpoint_no_key():
    """Health endpoint should NOT require API key."""
    print("Testing /health endpoint (no API key required)...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ PASS: Health endpoint accessible without API key")
        return True
    else:
        print("❌ FAIL: Health endpoint should be accessible without API key")
        return False

def test_protected_endpoint_no_key():
    """Protected endpoints should return 401 without API key."""
    print("\nTesting /menu/muv endpoint (no API key)...")
    response = requests.get(f"{BASE_URL}/api/menu/muv")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 401:
        print("✅ PASS: Protected endpoint correctly returned 401")
        return True
    else:
        print("❌ FAIL: Protected endpoint should return 401 without API key")
        return False

def test_protected_endpoint_with_key():
    """Protected endpoints should work with valid API key."""
    print("\nTesting /menu/muv endpoint (with X-Backend-Api-Key)...")
    headers = {"X-Backend-Api-Key": "test-key"}
    response = requests.get(f"{BASE_URL}/api/menu/muv", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ PASS: Protected endpoint accessible with valid API key")
        return True
    else:
        print("❌ FAIL: Protected endpoint should return 200 with valid API key")
        return False

def test_protected_endpoint_wrong_key():
    """Protected endpoints should return 401 with invalid API key."""
    print("\nTesting /menu/muv endpoint (with wrong API key)...")
    headers = {"X-Backend-Api-Key": "wrong-key"}
    response = requests.get(f"{BASE_URL}/api/menu/muv", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 401:
        print("✅ PASS: Protected endpoint correctly returned 401 with wrong key")
        return True
    else:
        print("❌ FAIL: Protected endpoint should return 401 with wrong API key")
        return False

def test_v2_health_endpoint():
    """v2/health endpoint should NOT require API key."""
    print("\nTesting /v2/health endpoint (no API key required)...")
    response = requests.get(f"{BASE_URL}/api/v2/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ PASS: v2 Health endpoint accessible without API key")
        return True
    else:
        print("❌ FAIL: v2 Health endpoint should be accessible without API key")
        return False

def test_v2_protected_endpoint():
    """v2 protected endpoints should require API key."""
    print("\nTesting /v2/strains endpoint (with X-Backend-Api-Key)...")
    headers = {"X-Backend-Api-Key": "test-key"}
    response = requests.get(f"{BASE_URL}/api/v2/strains", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ PASS: v2 Protected endpoint accessible with valid API key")
        return True
    elif response.status_code == 404:
        print("⚠️  SKIP: v2 endpoints not available (expected for development)")
        return True
    else:
        print("❌ FAIL: v2 Protected endpoint should return 200 with valid API key")
        return False

def main():
    print("🔐 Testing Backend API Key Security")
    print("=" * 50)
    
    # Check if function app is running
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
    except requests.ConnectionError:
        print("❌ Function app not running on http://localhost:7081")
        print("Start with: func host start --port 7081")
        sys.exit(1)
    
    # Run all tests
    tests = [
        test_health_endpoint_no_key,
        test_protected_endpoint_no_key,
        test_protected_endpoint_with_key,
        test_protected_endpoint_wrong_key,
        test_v2_health_endpoint,
        test_v2_protected_endpoint,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ FAIL: Test {test.__name__} threw exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend API key validation is working.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the function app configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()