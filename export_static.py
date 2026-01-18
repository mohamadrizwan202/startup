import re
import os
import shutil

# Define paths
template_path = 'templates/index.html'
static_src = 'static'
dist_dir = 'static_dist'
dist_html = os.path.join(dist_dir, 'index.html')
dist_static = os.path.join(dist_dir, 'static')

# Ensure dist directory exists
if os.path.exists(dist_dir):
    shutil.rmtree(dist_dir)
os.makedirs(dist_dir)

# Copy static files
shutil.copytree(static_src, dist_static)
print(f"Copied static files to {dist_static}")

# Read index.html
with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Inline _navbar.html
navbar_path = 'templates/_navbar.html'
if os.path.exists(navbar_path):
    with open(navbar_path, 'r', encoding='utf-8') as f:
        navbar_content = f.read()
    # Use regex for flexible matching of quotes and whitespace
    content = re.sub(r'\{\%\s*include\s*[\'"]_navbar\.html[\'"]\s*\%\}\s*', lambda m: navbar_content, content)
    print("Inlined _navbar.html")

# Fix request.path and csrf_token
content = re.sub(r'\{\{\s*request\.path\s*\}\}', '/', content)
content = re.sub(r'\{\{\s*csrf_token\(\)\s*\}\}', '', content)

# Remove Jinja2 auth blocks (assume logged out for static)
# Remove {% if current_user.is_authenticated %}...{% else %} part
content = re.sub(r'\{\%\s*if current_user\.is_authenticated\s*\%\}.*?\{\%\s*else\s*\%\}', '', content, flags=re.DOTALL)
# Remove closing {% endif %}
content = re.sub(r'\{\%\s*endif\s*\%\}\s*</div>', '</div>', content) # specific to navbar structure or generic cleanup

# Better approach for navbar auth: match the whole block
# Pattern: {% if current_user.is_authenticated %}(...){% else %}(...){% endif %}
# We want group 2.
auth_pattern = r'\{\%\s*if current_user\.is_authenticated\s*\%\}(.*?)(\{\%\s*else\s*\%\}(.*?))?\{\%\s*endif\s*\%\}'
def auth_repl(match):
    if match.group(3):
        return match.group(3)
    return "" 

content = re.sub(auth_pattern, auth_repl, content, flags=re.DOTALL)


# Replace css/js url_for
# Pattern: {{ url_for('static', filename='path/to/file') }}
# Replacement: static/path/to/file
content = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"static/\1", content)
content = re.sub(r'\{\{\s*url_for\("static",\s*filename="([^"]+)"\)\s*\}\}', r"static/\1", content)

# Replace url_for('index') -> index.html (or /)
content = re.sub(r"\{\{\s*url_for\('index'\)\s*\}\}", "index.html", content)
content = re.sub(r"\{\{\s*url_for\('login'\)\s*\}\}", "#login", content)
content = re.sub(r"\{\{\s*url_for\('register'\)\s*\}\}", "#register", content)
content = re.sub(r"\{\{\s*url_for\('contact'\)\s*\}\}", "#contact", content)
content = re.sub(r"\{\{\s*url_for\('logout'\)\s*\}\}", "index.html", content)

# Remove any remaining Jinja tags broadly if possible, or specific ones?
# Feedback include might also be there
feedback_path = 'templates/_feedback.html'
if os.path.exists(feedback_path):
    with open(feedback_path, 'r', encoding='utf-8') as f:
        feedback_content = f.read()
    # Use regex for flexible matching
    content = re.sub(r'\{\%\s*include\s*[\'"]_feedback\.html[\'"]\s*\%\}\s*', lambda m: feedback_content, content)
    print("Inlined _feedback.html")

# Write static index.html
with open(dist_html, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Created static index.html at {dist_html}")
print("Done.")
