#!/usr/bin/env python3
"""
Test script to demonstrate the admin workflow:
1. Login to admin
2. Fetch categories
3. Run populate_sample_data command
"""

import requests
import json
import subprocess
import sys

def test_admin_login():
    """Test admin login and return JWT token"""
    print("🔐 Testing admin login...")
    
    login_data = {
        "email": "admin@supplica.com",
        "password": "Admin@123"
    }
    
    try:
        response = requests.post(
            "http://127.0.0.1:8000/api/admin/login/",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        
        print(f"✅ Login successful!")
        print(f"   User: {user.get('email')}")
        print(f"   Superuser: {user.get('is_superuser')}")
        print(f"   Token: {token[:50]}...")
        
        return token
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Login failed: {e}")
        return None

def test_categories_api(token):
    """Test categories API with JWT token"""
    print("\n📂 Testing categories API...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            "http://127.0.0.1:8000/api/categories/admin/list/",
            headers=headers,
            params={"page_size": 100}
        )
        response.raise_for_status()
        
        data = response.json()
        categories = data.get("data", {}).get("categories", [])
        
        print(f"✅ Categories API working!")
        print(f"   Found {len(categories)} categories:")
        for cat in categories[:5]:  # Show first 5
            print(f"   - {cat.get('name')} (ID: {cat.get('id')})")
        if len(categories) > 5:
            print(f"   ... and {len(categories) - 5} more")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Categories API failed: {e}")
        return False

def test_populate_command(token):
    """Test the populate_sample_data command"""
    print(f"\n🚀 Testing populate_sample_data command...")
    
    try:
        result = subprocess.run([
            sys.executable, "manage.py", "populate_sample_data",
            "--admin-token", token
        ], capture_output=True, text=True, cwd=".")
        
        if result.returncode == 0:
            print("✅ Command executed successfully!")
            print("   Output:")
            for line in result.stdout.split('\n')[-10:]:  # Show last 10 lines
                if line.strip():
                    print(f"   {line}")
        else:
            print(f"❌ Command failed with return code {result.returncode}")
            print(f"   Error: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Command execution failed: {e}")
        return False

def main():
    """Main test workflow"""
    print("🧪 Testing Admin Workflow\n")
    
    # Test admin login
    token = test_admin_login()
    if not token:
        print("\n❌ Cannot proceed without valid token")
        return False
    
    # Test categories API
    if not test_categories_api(token):
        print("\n❌ Categories API not working")
        return False
    
    # Test populate command
    if not test_populate_command(token):
        print("\n❌ Populate command failed")
        return False
    
    print("\n🎉 All tests passed! Admin workflow is working correctly.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)