"""
Authorization utilities for enforcing least-privilege access control.

This module provides:
- require_admin() decorator for admin-only endpoints
- get_or_404_owned() helper for enforcing resource ownership
- AUTHZ_STRICT flag support for gradual rollout
"""
import os
from functools import wraps
from flask import abort, jsonify, request, session
from flask_login import current_user  # pyright: ignore[reportMissingImports]


# Authorization strictness flag
# When AUTHZ_STRICT=0, helpers behave permissively (backward compatible)
# When AUTHZ_STRICT=1, enforce proper 401/403/404 responses
AUTHZ_STRICT = os.getenv("AUTHZ_STRICT", "0").strip().lower() in ("1", "true", "yes", "on")


def is_admin():
    """
    Check if the current user is an admin.
    Currently checks for an 'is_admin' flag in the session or user object.
    Can be extended to check database roles if needed.
    """
    if not AUTHZ_STRICT:
        # Permissive mode: allow access
        return False
    
    # Check session for admin flag
    if session.get("is_admin"):
        return True
    
    # Check current_user if Flask-Login is active
    if hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
        if hasattr(current_user, "is_admin") and current_user.is_admin:
            return True
    
    return False


def require_admin(f):
    """
    Decorator to require admin privileges for an endpoint.
    
    When AUTHZ_STRICT=0: Allows access (backward compatible)
    When AUTHZ_STRICT=1: Returns 403 if user is not admin
    
    Usage:
        @app.route('/admin/users')
        @require_admin
        def admin_users():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if AUTHZ_STRICT and not is_admin():
            # Check if this is an API route
            if request.path.startswith("/api/"):
                return jsonify({"error": "admin_required"}), 403
            # For non-API routes, return 403 HTML
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def get_or_404_owned(model, id_field, id_value, owner_field="user_id", allow_admin=True):
    """
    Fetch a resource by ID and enforce ownership unless user is admin.
    
    Args:
        model: The database model/table name (string) or a function that returns a query
        id_field: The field name to match (e.g., "id", "recipe_id")
        id_value: The value to match
        owner_field: The field name that stores the owner ID (default: "user_id")
        allow_admin: If True, admins can access any resource (default: True)
    
    Returns:
        The resource row (dict) if found and owned by user (or admin)
    
    Raises:
        404: If resource not found or not owned by user (when AUTHZ_STRICT=1)
        401: If user not authenticated (when AUTHZ_STRICT=1)
    
    Example:
        # In a route handler:
        recipe = get_or_404_owned("recipes", "id", recipe_id, "user_id")
        return jsonify(recipe)
    """
    import db
    
    # Get current user ID
    user_id = session.get("user_id")
    
    # In permissive mode, skip ownership checks
    if not AUTHZ_STRICT:
        # Just fetch the resource without ownership check
        conn = db.get_conn()
        try:
            cursor = conn.cursor()
            query = db.prepare_query(f"SELECT * FROM {model} WHERE {id_field} = ?")
            cursor.execute(query, (id_value,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return db.row_to_dict(row, cursor)
            # Return None in permissive mode if not found
            return None
        except Exception:
            return None
    
    # Strict mode: enforce authentication and ownership
    if not user_id:
        if request.path.startswith("/api/"):
            return jsonify({"error": "auth_required"}), 401
        abort(401)
    
    # Check if user is admin (if allowed)
    is_user_admin = allow_admin and is_admin()
    
    # Fetch the resource
    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        query = db.prepare_query(f"SELECT * FROM {model} WHERE {id_field} = ?")
        cursor.execute(query, (id_value,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            # Resource not found
            if request.path.startswith("/api/"):
                return jsonify({"error": "not_found"}), 404
            abort(404)
        
        resource = db.row_to_dict(row, cursor)
        
        # Check ownership (unless admin)
        if not is_user_admin:
            resource_owner_id = resource.get(owner_field)
            if resource_owner_id != user_id:
                # User doesn't own this resource
                if request.path.startswith("/api/"):
                    return jsonify({"error": "forbidden"}), 404  # 404 to hide existence
                abort(404)
        
        return resource
    except Exception as e:
        # Database error
        if request.path.startswith("/api/"):
            return jsonify({"error": "database_error"}), 500
        abort(500)

