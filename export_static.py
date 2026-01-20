import re
import os
import shutil

# Define paths
template_dir = 'templates'
static_src = 'static'
dist_dir = 'static_dist'
dist_static = os.path.join(dist_dir, 'static')

# Ensure dist directory exists
if os.path.exists(dist_dir):
    shutil.rmtree(dist_dir)
os.makedirs(dist_dir)

# Copy static files
shutil.copytree(static_src, dist_static)
print(f"Copied static files to {dist_static}")

# Copy favicon and logos to root of dist as well
for f in ['favicon.svg', 'logo.svg', 'logo-white.svg']:
    if os.path.exists(f):
        shutil.copy(f, dist_dir)
        print(f"Copied {f} to {dist_dir}")

# Templates to export (template_name, output_name)
pages_to_export = [
    ('index.html', 'index.html'),
    ('about.html', 'about.html'),
    ('contact.html', 'contact.html'),
    ('pricing.html', 'pricing.html'),
    ('login.html', 'login.html'),
    ('register.html', 'register.html'),
    ('browser.html', 'browser.html'),
    ('index_docs.html', 'index_docs.html'),
]

# Common replacements
def process_jinja_content(content):
    # Inline _navbar.html
    navbar_path = os.path.join(template_dir, '_navbar.html')
    if os.path.exists(navbar_path):
        with open(navbar_path, 'r', encoding='utf-8') as f:
            navbar_content = f.read()
        content = re.sub(r'\{\%\s*include\s*[\'"]_navbar\.html[\'"]\s*\%\}\s*', lambda m: navbar_content, content)

    # Inline _feedback.html
    feedback_path = os.path.join(template_dir, '_feedback.html')
    if os.path.exists(feedback_path):
        with open(feedback_path, 'r', encoding='utf-8') as f:
            feedback_content = f.read()
        content = re.sub(r'\{\%\s*include\s*[\'"]_feedback\.html[\'"]\s*\%\}\s*', lambda m: feedback_content, content)

    # Fix request.path and csrf_token
    content = re.sub(r'\{\{\s*request\.path\s*\}\}', '/', content)
    content = re.sub(r'\{\{\s*csrf_token\(\)\s*\}\}', '', content)
    
    # Handle current_user.is_authenticated blocks (assume logged out)
    auth_pattern = r'\{\%\s*if current_user\.is_authenticated\s*\%\}(.*?)(\{\%\s*else\s*\%\}(.*?))?\{\%\s*endif\s*\%\}'
    def auth_repl(match):
        if match.group(3):
            return match.group(3)
        return ""
    content = re.sub(auth_pattern, auth_repl, content, flags=re.DOTALL)

    # Replace css/js url_for
    content = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"static/\1", content)
    content = re.sub(r'\{\{\s*url_for\("static",\s*filename="([^"]+)"\)\s*\}\}', r"static/\1", content)

    # Replace url_for for pages
    content = re.sub(r"\{\{\s*url_for\('index'\)\s*\}\}", "index.html", content)
    content = re.sub(r"\{\{\s*url_for\('about'\)\s*\}\}", "about.html", content)
    content = re.sub(r"\{\{\s*url_for\('contact'\)\s*\}\}", "contact.html", content)
    content = re.sub(r"\{\{\s*url_for\('pricing'\)\s*\}\}", "pricing.html", content)
    content = re.sub(r"\{\{\s*url_for\('login'\)\s*\}\}", "login.html", content)
    content = re.sub(r"\{\{\s*url_for\('register'\)\s*\}\}", "register.html", content)
    content = re.sub(r"\{\{\s*url_for\('logout'\)\s*\}\}", "index.html", content)

    # Remove any canonical domain helpers if they are using {{ request.path }}
    # e.g. https://purefyul.com{{ request.path }} -> https://purefyul.com/
    content = re.sub(r'https://purefyul\.com\{\{\s*request\.path\s*\}\}', 'https://purefyul.com/', content)

    # Clean up common Jinja tags
    content = re.sub(r'nonce="\{\{\s*csp_nonce\s*\}\}"', '', content)
    content = re.sub(r'\{\{\s*csp_nonce\s*\}\}', '', content)
    
    # Remove flash message blocks
    flash_pattern = r'\{\%\s*with\s*messages\s*=\s*get_flashed_messages\(.*?\)\s*\%\}.*?\{\%\s*endwith\s*\%\}'
    content = re.sub(flash_pattern, '', content, flags=re.DOTALL)
    
    # Simple check for any remaining loops/ifs that might be around flash messages or other dynamic parts
    content = re.sub(r'\{\%\s*if messages\s*\%\}.*?\{\%\s*endif\s*\%\}', '', content, flags=re.DOTALL)

    # Clean up form values
    content = re.sub(r'value="\{\{\s*request\.form\..*?\}\}"', 'value=""', content)
    content = re.sub(r'\{\{\s*request\.form\..*?\}\}', '', content)
    
    # Clean up selected/checked logic in forms
    content = re.sub(r'\{\{\s*\'selected\'.*?\}\}', '', content)
    content = re.sub(r'\{\{\s*\'checked\'.*?\}\}', '', content)

    # Remove server time in index_docs
    content = re.sub(r'Server Time: \{\{.*?\}\}', 'Server Time: Static Build', content)

    # Final cleanup of remaining tags (crude but helpful for a static site)
    content = re.sub(r'\{\{.*?\}\}', '', content)
    content = re.sub(r'\{\%.*?\%\}', '', content)

    return content

for template_name, output_name in pages_to_export:
    input_path = os.path.join(template_dir, template_name)
    output_path = os.path.join(dist_dir, output_name)
    
    if os.path.exists(input_path):
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = process_jinja_content(content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created {output_path}")
    else:
        print(f"Warning: {input_path} not found.")

print("Static export complete.")
