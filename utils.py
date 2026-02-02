import os

def find_nearest_readme(file_path, repo_file_list):
    """
    Given a file path like 'src/api/user.py', this function searches 
    for a README.md in 'src/api/', then 'src/', then root.
    """
    current_dir = os.path.dirname(file_path)
    max_levels = 10
    levels = 0

    while levels < max_levels:
        if current_dir == "" or current_dir == ".":
            potential_readme = "README.md"
        else:
            potential_readme = f"{current_dir}/README.md"
            
        # Clean up path separators for Windows/Linux compatibility
        potential_readme = potential_readme.replace("\\", "/")
        
        if potential_readme in repo_file_list:
            return potential_readme
        
        if current_dir == "" or current_dir == ".":
            break
            
        current_dir = os.path.dirname(current_dir)
        levels += 1
        
    return "README.md"