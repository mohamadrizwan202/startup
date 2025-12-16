#!/bin/bash
# Test script for /__dbcheck endpoint
# Usage: ./test_dbcheck.sh

TOKEN="yIqGqoyXI0UeoH0sklJsXjksvRHEldrewouz4vctCQU"
URL="https://startup-hmwd.onrender.com/__dbcheck"

echo "Testing /__dbcheck endpoint..."
echo "URL: $URL"
echo ""

response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -H "Authorization: Bearer $TOKEN" "$URL")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

echo "HTTP Status: $http_code"
echo ""
echo "Response:"
echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
echo ""

if [ "$http_code" = "200" ]; then
    echo "✓ Success! Endpoint is working correctly."
elif [ "$http_code" = "404" ]; then
    echo "✗ 404 Not Found - Make sure:"
    echo "  1. DBCHECK_TOKEN is set in Render environment variables"
    echo "  2. The service has been redeployed after setting the token"
    echo "  3. You're using the correct token: $TOKEN"
elif [ "$http_code" = "403" ]; then
    echo "✗ 403 Forbidden - Token mismatch. Check that DBCHECK_TOKEN in Render matches the token above."
elif [ "$http_code" = "500" ]; then
    echo "✗ 500 Server Error - DBCHECK_TOKEN environment variable is not set in Render."
else
    echo "✗ Unexpected status code: $http_code"
fi

