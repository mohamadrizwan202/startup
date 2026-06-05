# ── FORGOT PASSWORD ROUTES ───────────────────────────────────────────────────

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Show forgot password form and send reset email."""
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    if not email:
        return render_template("forgot_password.html", error="Please enter your email address.")

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        else:
            cursor.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()

        if row:
            user = db.row_to_dict(row)
            # Generate secure token
            token = secrets.token_urlsafe(32)
            expiry = (datetime.now(timezone.utc).replace(tzinfo=None) +
                      __import__('datetime').timedelta(hours=1)).isoformat()

            # Save token to DB
            if db.USE_POSTGRES:
                cursor.execute(
                    "UPDATE users SET reset_token = %s, reset_token_expiry = %s WHERE id = %s",
                    (token, expiry, user["id"])
                )
            else:
                cursor.execute(
                    "UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
                    (token, expiry, user["id"])
                )
            conn.commit()

            # Build reset link
            base_url = request.host_url.rstrip("/")
            reset_link = f"{base_url}/reset-password/{token}"

            # Send email
            try:
                send_hostinger_email(
                    to_email=email,
                    subject="Reset your PureFyul password",
                    text_body=f"""Hi,

We received a request to reset your PureFyul password.

Click the link below to reset your password (valid for 1 hour):

{reset_link}

If you didn't request this, you can safely ignore this email. Your password won't change.

— The PureFyul Team
purefyul.com
"""
                )
            except Exception as e:
                app.logger.error(f"Failed to send reset email: {e}")

    finally:
        conn.close()

    # Always show success (don't reveal if email exists)
    return render_template("forgot_password.html", success=True)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Validate token and allow user to set new password."""
    import datetime as dt
    from werkzeug.security import generate_password_hash

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "SELECT id, email, reset_token_expiry FROM users WHERE reset_token = %s",
                (token,)
            )
        else:
            cursor.execute(
                "SELECT id, email, reset_token_expiry FROM users WHERE reset_token = ?",
                (token,)
            )
        row = cursor.fetchone()

        if not row:
            return render_template("reset_password.html", error="Invalid or expired reset link.", token=token, invalid=True)

        user = db.row_to_dict(row)

        # Check expiry
        expiry_str = user.get("reset_token_expiry")
        if not expiry_str:
            return render_template("reset_password.html", error="Invalid or expired reset link.", token=token, invalid=True)

        try:
            expiry_dt = dt.datetime.fromisoformat(expiry_str)
            if dt.datetime.utcnow() > expiry_dt:
                return render_template("reset_password.html", error="This reset link has expired. Please request a new one.", token=token, invalid=True)
        except Exception:
            return render_template("reset_password.html", error="Invalid reset link.", token=token, invalid=True)

        if request.method == "GET":
            return render_template("reset_password.html", token=token, email=user["email"])

        # POST — update password
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not password or len(password) < 8:
            return render_template("reset_password.html", token=token, email=user["email"],
                                   error="Password must be at least 8 characters.")

        if password != confirm:
            return render_template("reset_password.html", token=token, email=user["email"],
                                   error="Passwords do not match.")

        hashed = generate_password_hash(password)

        if db.USE_POSTGRES:
            cursor.execute(
                "UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expiry = NULL WHERE id = %s",
                (hashed, user["id"])
            )
        else:
            cursor.execute(
                "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
                (hashed, user["id"])
            )
        conn.commit()

        return render_template("reset_password.html", success=True)

    finally:
        conn.close()
