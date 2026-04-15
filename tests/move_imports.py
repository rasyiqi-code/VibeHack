import re

with open('tests/test_guardrails.py', 'r') as f:
    content = f.read()

imports = [
    "from unittest.mock import patch\n",
    "from vibehack.guardrails.waiver import verify_unchained_access\n"
]

for imp in imports:
    content = content.replace(imp, "")

import_section_match = re.search(r'import pytest\nfrom vibehack\.guardrails\.regex_engine import check_command, check_target\n', content)

if import_section_match:
    import_index = import_section_match.end()
    new_content = content[:import_index] + imports[0] + imports[1] + content[import_index:]
    with open('tests/test_guardrails.py', 'w') as f:
        f.write(new_content)
