#!/usr/bin/env python3
"""Manual test script to verify API endpoints work correctly."""

import requests
import json
import sys

def test_api_endpoint(base_url="http://localhost:8084"):
    """Test API endpoints manually."""
    
    print(f"Testing API endpoints at: {base_url}")
    print("=" * 50)
    
    # Test 1: Test command (should work without API key)
    print("1. Testing 'test' command (no API key required):")
    try:
        response = requests.get(f"{base_url}/api?cmd=test")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 2: Help command
    print("2. Testing 'help' command:")
    try:
        response = requests.get(f"{base_url}/api?cmd=help")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 3: listProviders without API key (should fail)
    print("3. Testing 'listProviders' without API key (should fail):")
    try:
        response = requests.get(f"{base_url}/api?cmd=listProviders")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        print()
    except Exception as e:
        print(f"   ERROR: {e}")
        print()
    
    # Test 4: Try to get API key from logs or manual input
    print("4. To test with API key, you need to:")
    print("   - Check application logs for 'API Key for Prowlarr integration: <key>'")
    print("   - Or run: docker exec <container> cat data/api_key.txt")
    print()
    
    api_key = input("Enter API key (or press Enter to skip API key tests): ").strip()
    
    if api_key:
        # Test 5: listProviders with API key
        print("5. Testing 'listProviders' with API key:")
        try:
            response = requests.get(f"{base_url}/api?cmd=listProviders&apikey={api_key}")
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Response structure:")
                print(f"     - Has 'Data' key: {'Data' in data}")
                print(f"     - Newznabs count: {len(data.get('Data', {}).get('Newznabs', []))}")
                print(f"     - Torznabs count: {len(data.get('Data', {}).get('Torznabs', []))}")
                print(f"     - RSS count: {len(data.get('Data', {}).get('RSS', []))}")
                print(f"   Full Response: {json.dumps(data, indent=2)}")
            else:
                print(f"   Error Response: {json.dumps(response.json(), indent=2)}")
            print()
        except Exception as e:
            print(f"   ERROR: {e}")
            print()
        
        # Test 6: changeProvider with API key
        print("6. Testing 'changeProvider' with API key:")
        try:
            params = {
                'cmd': 'changeProvider',
                'apikey': api_key,
                'name': 'TestProvider',
                'host': 'https://test.example.com',
                'type': 'newznab',
                'prov_apikey': 'test-key',
                'enabled': 'true',
                'categories': '7000,7020',
                'priority': '1'
            }
            response = requests.get(f"{base_url}/api", params=params)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {json.dumps(response.json(), indent=2)}")
            print()
        except Exception as e:
            print(f"   ERROR: {e}")
            print()
    
    print("API testing complete!")

if __name__ == '__main__':
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8084"
    test_api_endpoint(base_url)