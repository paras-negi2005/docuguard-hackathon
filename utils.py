import os

def find_nearest_readme(file_path, repo_file_list):
    """
    Given a file path like 'src/api/user.py', this function searches 
    for a README.md in 'src/api/', then 'src/', then root.
    """
    # Start at the directory of the changed file
    current_dir = os.path.dirname(file_path)
    
    # Safety check: Prevent infinite loops
    max_levels = 10
    levels = 0

    while levels < max_levels:
        # construct the potential path
        if current_dir == "" or current_dir == ".":
            potential_readme = "README.md"
        else:
            potential_readme = f"{current_dir}/README.md"
            
        # Clean up path separators
        potential_readme = potential_readme.replace("\\", "/")
        
        # Check if this README exists in the repo's file list
        if potential_readme in repo_file_list:
            return potential_readme
        
        # Stop if we hit the root
        if current_dir == "" or current_dir == ".":
            break
            
        # Move up one folder
        current_dir = os.path.dirname(current_dir)
        levels += 1
        
    # Default fallback
    return "README.md"