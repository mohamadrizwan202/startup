#!/usr/bin/env python3
"""
API Smoke Test for Nutrition & Allergen Database API

This script performs basic smoke tests on the Flask API endpoints
to verify they are responding correctly.

Usage:
    python3 api_smoke_test.py [--base-url BASE_URL] [--verbose]

Environment Variables:
    BASE_URL: Base URL for the API (default: http://localhost:8000)
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, Any, Optional

# Default configuration
DEFAULT_BASE_URL = os.environ.get("BASE_URL", "https://startup-hmwd.onrender.com")
DEFAULT_TIMEOUT = 40  # seconds


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    """Print success message in green"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message in red"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def test_endpoint(
    method: str,
    url: str,
    expected_status: int = 200,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    verbose: bool = False
) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Test an API endpoint
    
    Returns:
        (success: bool, response_data: dict|None, error_message: str|None)
    """
    try:
        if verbose:
            print_info(f"Testing {method} {url}")
        
        if method.upper() == "GET":
            response = requests.get(url, timeout=DEFAULT_TIMEOUT, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(
                url,
                json=data,
                timeout=DEFAULT_TIMEOUT,
                headers=headers or {"Content-Type": "application/json"}
            )
        else:
            return False, None, f"Unsupported method: {method}"
        
        success = response.status_code == expected_status
        
        try:
            response_data = response.json() if response.content else None
        except json.JSONDecodeError:
            response_data = {"raw": response.text[:200]}
        
        if not success:
            error_msg = f"Expected status {expected_status}, got {response.status_code}"
            if response_data:
                error_msg += f": {json.dumps(response_data, indent=2)[:200]}"
            return False, response_data, error_msg
        
        return True, response_data, None
        
    except requests.exceptions.ConnectionError:
        return False, None, "Connection refused - is the server running?"
    except requests.exceptions.Timeout:
        return False, None, f"Request timed out after {DEFAULT_TIMEOUT}s"
    except requests.exceptions.RequestException as e:
        return False, None, f"Request failed: {str(e)}"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"


def test_home_page(base_url: str, verbose: bool = False) -> bool:
    """Test the home page endpoint"""
    print("\n" + "="*60)
    print("Testing Home Page")
    print("="*60)
    
    success, data, error = test_endpoint("GET", f"{base_url}/", verbose=verbose)
    
    if success:
        print_success("GET / - Home page loads successfully")
        return True
    else:
        print_error(f"GET / - {error}")
        return False


def test_categories_endpoint(base_url: str, verbose: bool = False) -> bool:
    """Test the categories endpoint"""
    print("\n" + "="*60)
    print("Testing Categories Endpoint")
    print("="*60)
    
    success, data, error = test_endpoint("GET", f"{base_url}/api/categories", verbose=verbose)
    
    if success:
        if isinstance(data, list) and len(data) > 0:
            print_success(f"GET /api/categories - Returns {len(data)} categories")
            if verbose:
                print_info(f"Sample categories: {', '.join(data[:5])}")
            return True
        else:
            print_warning("GET /api/categories - Returns empty list or invalid format")
            return False
    else:
        print_error(f"GET /api/categories - {error}")
        return False


def test_category_hierarchy_endpoint(base_url: str, verbose: bool = False) -> bool:
    """Test the category hierarchy endpoint"""
    print("\n" + "="*60)
    print("Testing Category Hierarchy Endpoint")
    print("="*60)
    
    success, data, error = test_endpoint("GET", f"{base_url}/api/category-hierarchy", verbose=verbose)
    
    if success:
        if isinstance(data, dict) and len(data) > 0:
            print_success(f"GET /api/category-hierarchy - Returns {len(data)} top-level categories")
            if verbose:
                sample_cat = list(data.keys())[0]
                print_info(f"Sample category: {sample_cat} with {len(data[sample_cat])} subcategories")
            return True
        else:
            print_warning("GET /api/category-hierarchy - Returns empty dict or invalid format")
            return False
    else:
        print_error(f"GET /api/category-hierarchy - {error}")
        return False


def test_ingredients_endpoint(base_url: str, verbose: bool = False) -> bool:
    """Test the ingredients endpoint with a sample category"""
    print("\n" + "="*60)
    print("Testing Ingredients Endpoint")
    print("="*60)
    
    # First, get a list of categories to test with
    success, categories, error = test_endpoint("GET", f"{base_url}/api/categories", verbose=False)
    
    if not success or not categories or len(categories) == 0:
        print_warning("Cannot test /api/ingredients/<category> - No categories available")
        return False
    
    # Use the first category
    test_category = categories[0]
    test_url = f"{base_url}/api/ingredients/{test_category}"
    
    success, data, error = test_endpoint("GET", test_url, verbose=verbose)
    
    if success:
        if isinstance(data, list):
            print_success(f"GET /api/ingredients/{test_category} - Returns {len(data)} ingredients")
            if verbose and len(data) > 0:
                print_info(f"Sample ingredient: {data[0].get('name', 'N/A')}")
            return True
        else:
            print_warning(f"GET /api/ingredients/{test_category} - Returns invalid format")
            return False
    else:
        print_error(f"GET /api/ingredients/{test_category} - {error}")
        return False


def test_analyze_endpoint(base_url: str, verbose: bool = False) -> bool:
    """Test the analyze endpoint"""
    print("\n" + "="*60)
    print("Testing Analyze Endpoint")
    print("="*60)
    
    test_data = {
        "ingredients": ["banana", "spinach", "almond milk"]
    }
    
    success, data, error = test_endpoint("POST", f"{base_url}/api/analyze", data=test_data, verbose=verbose)
    
    if success:
        print_success("POST /api/analyze - Analyzes ingredients successfully")
        if verbose and data:
            print_info(f"Response keys: {', '.join(data.keys()) if isinstance(data, dict) else 'N/A'}")
        return True
    else:
        print_error(f"POST /api/analyze - {error}")
        return False


def test_nlp_query_endpoint(base_url: str, verbose: bool = False) -> bool:
    """Test the NLP query endpoint"""
    print("\n" + "="*60)
    print("Testing NLP Query Endpoint")
    print("="*60)
    
    test_data = {
        "query": "chicken breast and broccoli"
    }
    
    success, data, error = test_endpoint("POST", f"{base_url}/nlp-query", data=test_data, verbose=verbose)
    
    if success:
        print_success("POST /nlp-query - Processes NLP query successfully")
        if verbose and data:
            print_info(f"Response keys: {', '.join(data.keys()) if isinstance(data, dict) else 'N/A'}")
        return True
    else:
        print_error(f"POST /nlp-query - {error}")
        return False


def run_all_tests(base_url: str, verbose: bool = False) -> Dict[str, bool]:
    """Run all smoke tests"""
    results = {}
    
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("="*60)
    print("API Smoke Test Suite")
    print("="*60)
    print(f"Base URL: {base_url}")
    print(f"{Colors.RESET}")
    
    # Run tests
    results["home"] = test_home_page(base_url, verbose)
    results["categories"] = test_categories_endpoint(base_url, verbose)
    results["category_hierarchy"] = test_category_hierarchy_endpoint(base_url, verbose)
    results["ingredients"] = test_ingredients_endpoint(base_url, verbose)
    results["analyze"] = test_analyze_endpoint(base_url, verbose)
    results["nlp_query"] = test_nlp_query_endpoint(base_url, verbose)
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.RESET} - {test_name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}All tests passed! ✓{Colors.RESET}")
        return results
    else:
        print(f"{Colors.RED}{Colors.BOLD}Some tests failed ✗{Colors.RESET}")
        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="API Smoke Test for Nutrition & Allergen Database API"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL for the API (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Run tests
    results = run_all_tests(args.base_url, args.verbose)
    
    # Exit with appropriate code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

