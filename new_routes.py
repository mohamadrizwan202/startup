# ── PLAN CHECK HELPER ────────────────────────────────────────────────────────

def get_user_plan(user_id):
    """Returns 'free' or 'pro' for a given user."""
    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "SELECT plan FROM subscriptions WHERE user_id = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
        else:
            cursor.execute(
                "SELECT plan FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
        row = cursor.fetchone()
        if row:
            return db.row_to_dict(row)["plan"]
        return "free"
    finally:
        conn.close()


# ── SAVED RECIPES ─────────────────────────────────────────────────────────────

@app.route("/api/recipes", methods=["GET"])
@login_required
def get_recipes():
    """Get all saved recipes for the logged-in user."""
    import json
    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "SELECT * FROM saved_recipes WHERE user_id = %s ORDER BY created_at DESC",
                (current_user.id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM saved_recipes WHERE user_id = ? ORDER BY created_at DESC",
                (current_user.id,)
            )
        rows = cursor.fetchall()
        recipes = []
        for row in rows:
            r = db.row_to_dict(row)
            if isinstance(r.get("ingredients"), str):
                r["ingredients"] = json.loads(r["ingredients"])
            if isinstance(r.get("nutrition_summary"), str):
                r["nutrition_summary"] = json.loads(r["nutrition_summary"] or "{}")
            recipes.append(r)
        return jsonify({"recipes": recipes})
    finally:
        conn.close()


@app.route("/api/recipes", methods=["POST"])
@login_required
@csrf.exempt
def save_recipe():
    """Save a new recipe for the logged-in user (Pro only)."""
    import json
    if get_user_plan(current_user.id) == "free":
        return jsonify({
            "error": "upgrade_required",
            "message": "Saving recipes is a Pro feature. Upgrade for $4.99/month."
        }), 403

    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    ingredients = data.get("ingredients", [])
    nutrition_summary = data.get("nutrition_summary", {})
    health_goal = data.get("health_goal", "")
    notes = data.get("notes", "")

    if not name or not ingredients:
        return jsonify({"error": "Name and ingredients are required"}), 400

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                """INSERT INTO saved_recipes
                   (user_id, name, ingredients, nutrition_summary, health_goal, notes)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    current_user.id,
                    name,
                    json.dumps(ingredients),
                    json.dumps(nutrition_summary),
                    health_goal,
                    notes,
                )
            )
            result = cursor.fetchone()
            new_id = db.row_to_dict(result)["id"]
        else:
            cursor.execute(
                """INSERT INTO saved_recipes
                   (user_id, name, ingredients, nutrition_summary, health_goal, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    current_user.id,
                    name,
                    json.dumps(ingredients),
                    json.dumps(nutrition_summary),
                    health_goal,
                    notes,
                )
            )
            new_id = cursor.lastrowid
        conn.commit()
        return jsonify({"success": True, "id": new_id})
    finally:
        conn.close()


@app.route("/api/recipes/<int:recipe_id>", methods=["DELETE"])
@login_required
@csrf.exempt
def delete_recipe(recipe_id):
    """Delete a saved recipe (owner only)."""
    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "DELETE FROM saved_recipes WHERE id = %s AND user_id = %s",
                (recipe_id, current_user.id)
            )
        else:
            cursor.execute(
                "DELETE FROM saved_recipes WHERE id = ? AND user_id = ?",
                (recipe_id, current_user.id)
            )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


# ── MEAL PLANS ────────────────────────────────────────────────────────────────

@app.route("/api/mealplans", methods=["GET"])
@login_required
def get_meal_plans():
    """Get all meal plans for the logged-in user."""
    import json
    if get_user_plan(current_user.id) == "free":
        return jsonify({
            "error": "upgrade_required",
            "message": "Meal planning is a Pro feature. Upgrade for $4.99/month."
        }), 403

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "SELECT * FROM meal_plans WHERE user_id = %s ORDER BY created_at DESC",
                (current_user.id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM meal_plans WHERE user_id = ? ORDER BY created_at DESC",
                (current_user.id,)
            )
        plans = []
        for row in cursor.fetchall():
            r = db.row_to_dict(row)
            if isinstance(r.get("slots"), str):
                r["slots"] = json.loads(r["slots"])
            plans.append(r)
        return jsonify({"plans": plans})
    finally:
        conn.close()


@app.route("/api/mealplans", methods=["POST"])
@login_required
@csrf.exempt
def save_meal_plan():
    """Save a meal plan for the logged-in user (Pro only)."""
    import json
    if get_user_plan(current_user.id) == "free":
        return jsonify({
            "error": "upgrade_required",
            "message": "Meal planning is a Pro feature. Upgrade for $4.99/month."
        }), 403

    data = request.get_json(force=True) or {}
    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                """INSERT INTO meal_plans (user_id, name, week_start, slots)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (
                    current_user.id,
                    data.get("name", "My Meal Plan"),
                    data.get("week_start"),
                    json.dumps(data.get("slots", {}))
                )
            )
            result = cursor.fetchone()
            new_id = db.row_to_dict(result)["id"]
        else:
            cursor.execute(
                """INSERT INTO meal_plans (user_id, name, week_start, slots)
                   VALUES (?, ?, ?, ?)""",
                (
                    current_user.id,
                    data.get("name", "My Meal Plan"),
                    data.get("week_start"),
                    json.dumps(data.get("slots", {}))
                )
            )
            new_id = cursor.lastrowid
        conn.commit()
        return jsonify({"success": True, "id": new_id})
    finally:
        conn.close()


@app.route("/api/mealplans/<int:plan_id>", methods=["DELETE"])
@login_required
@csrf.exempt
def delete_meal_plan(plan_id):
    """Delete a meal plan (owner only)."""
    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "DELETE FROM meal_plans WHERE id = %s AND user_id = %s",
                (plan_id, current_user.id)
            )
        else:
            cursor.execute(
                "DELETE FROM meal_plans WHERE id = ? AND user_id = ?",
                (plan_id, current_user.id)
            )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


# ── EXPORT ────────────────────────────────────────────────────────────────────

@app.route("/api/recipes/export")
@login_required
def export_recipes():
    """Export all saved recipes as CSV (Pro only)."""
    import json
    import csv
    import io
    from flask import Response

    if get_user_plan(current_user.id) == "free":
        return jsonify({
            "error": "upgrade_required",
            "message": "Export is a Pro feature. Upgrade for $4.99/month."
        }), 403

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        if db.USE_POSTGRES:
            cursor.execute(
                "SELECT * FROM saved_recipes WHERE user_id = %s ORDER BY created_at DESC",
                (current_user.id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM saved_recipes WHERE user_id = ? ORDER BY created_at DESC",
                (current_user.id,)
            )
        rows = [db.row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Health Goal", "Ingredients", "Calories", "Protein(g)", "Carbs(g)", "Fat(g)", "Fiber(g)", "Sugar(g)", "Notes", "Saved On"])
    for r in rows:
        nutrition = json.loads(r.get("nutrition_summary") or "{}")
        ingredients = json.loads(r.get("ingredients") or "[]")
        ingredient_names = ", ".join([i.get("name", str(i)) if isinstance(i, dict) else str(i) for i in ingredients])
        writer.writerow([
            r.get("name", ""),
            r.get("health_goal", ""),
            ingredient_names,
            nutrition.get("calories", ""),
            nutrition.get("protein", ""),
            nutrition.get("carbs", ""),
            nutrition.get("fat", ""),
            nutrition.get("fiber", ""),
            nutrition.get("sugar", ""),
            r.get("notes", ""),
            r.get("created_at", "")
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=purefyul_recipes.csv"}
    )


# ── USER PLAN STATUS ──────────────────────────────────────────────────────────

@app.route("/api/plan", methods=["GET"])
@login_required
def get_plan():
    """Return the current user's plan (free or pro)."""
    plan = get_user_plan(current_user.id)
    return jsonify({"plan": plan})
