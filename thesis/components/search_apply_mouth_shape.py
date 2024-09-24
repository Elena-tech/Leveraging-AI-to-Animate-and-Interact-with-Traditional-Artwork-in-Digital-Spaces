def search_apply_mouth_shape_usage(file_content):
    lines = file_content.splitlines()
    method_definition = None
    method_usages = []

    for idx, line in enumerate(lines):
        if 'def apply_mouth_shape' in line:
            method_definition = (idx, line.strip())
        if 'apply_mouth_shape(' in line and 'def apply_mouth_shape' not in line:
            method_usages.append((idx, line.strip()))

    return method_definition, method_usages

# Load the content of artwork_animator.py
file_path = 'components/artwork_animator.py'

with open(file_path, 'r') as file:
    artwork_animator_code = file.read()

method_definition, method_usages = search_apply_mouth_shape_usage(artwork_animator_code)

print("Method Definition:", method_definition)
print("Method Usages:", method_usages)
