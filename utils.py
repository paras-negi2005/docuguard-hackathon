import os

def find_nearest_readme(file_path, all_files):
    """
    Finds the README.md in the same directory or parent directories.
    """
    current_dir = os.path.dirname(file_path)
    
    # Check current directory first
    expected = os.path.join(current_dir, "README.md").replace("\\", "/")
    if expected in all_files:
        return expected
        
    # Fallback to root README.md
    if "README.md" in all_files:
        return "README.md"
        
    return None