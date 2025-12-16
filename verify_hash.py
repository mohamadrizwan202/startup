#!/usr/bin/env python3
"""
Temporary script to verify password hashing in the database.
Queries the users table to check if passwords are stored as hashes.
"""
import sys
from db import get_conn

def verify_password_hash():
    """Query the database for a test user and display their password hash"""
    try:
        # Connect to database
        conn = get_conn()
        cursor = conn.cursor()
        
        # Query for the test user
        email = 'security_test@example.com'
        
        # Use appropriate query syntax based on database type
        from db import USE_POSTGRES
        if USE_POSTGRES:
            query = "SELECT email, password_hash FROM users WHERE email = %s"
        else:
            query = "SELECT email, password_hash FROM users WHERE email = ?"
        
        cursor.execute(query, (email,))
        result = cursor.fetchone()
        
        if result:
            # Handle both dict (PostgreSQL) and Row (SQLite) results
            if isinstance(result, dict):
                user_email = result.get('email')
                password_hash = result.get('password_hash')
            else:
                user_email = result[0]
                password_hash = result[1]
            
            print("=" * 70)
            print("PASSWORD HASH VERIFICATION")
            print("=" * 70)
            print(f"Email: {user_email}")
            print(f"\nPassword Hash: {password_hash}")
            print(f"\nHash Length: {len(password_hash) if password_hash else 0} characters")
            print(f"\nHash Format: {'pbkdf2:sha256' if password_hash and password_hash.startswith('pbkdf2:sha256') else 'Unknown'}")
            print("=" * 70)
            
            # Verify it's a hash and not plain text
            if password_hash and password_hash.startswith('pbkdf2:sha256:'):
                print("\n✓ Password is properly hashed (starts with 'pbkdf2:sha256:')")
            elif password_hash and len(password_hash) > 50:
                print("\n⚠ Password appears to be hashed (long string), but format is unexpected")
            else:
                print("\n✗ WARNING: Password does not appear to be hashed!")
        else:
            print(f"✗ User '{email}' not found in database.")
            print("\nShowing password hash for first available user instead:")
            print("-" * 70)
            
            # Query for first user
            if USE_POSTGRES:
                query = "SELECT email, password_hash FROM users ORDER BY email LIMIT 1"
                cursor.execute(query)
            else:
                query = "SELECT email, password_hash FROM users ORDER BY email LIMIT 1"
                cursor.execute(query)
            
            first_user = cursor.fetchone()
            if first_user:
                if isinstance(first_user, dict):
                    user_email = first_user.get('email')
                    password_hash = first_user.get('password_hash')
                else:
                    user_email = first_user[0]
                    password_hash = first_user[1]
                
                print(f"Email: {user_email}")
                print(f"\nPassword Hash: {password_hash}")
                print(f"\nHash Length: {len(password_hash) if password_hash else 0} characters")
                print(f"\nHash Format: {'pbkdf2:sha256' if password_hash and password_hash.startswith('pbkdf2:sha256') else 'Unknown'}")
                
                if password_hash and password_hash.startswith('pbkdf2:sha256:'):
                    print("\n✓ Password is properly hashed (starts with 'pbkdf2:sha256:')")
                else:
                    print("\n⚠ Password format unexpected")
            else:
                print("No users found in database.")
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    verify_password_hash()

