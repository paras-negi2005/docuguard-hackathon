import os

def find_nearest_readme(file_path, repo_file_list):
    """
    Given a file like 'src/components/button.py',
    finds 'src/components/README.md', then 'src/README.md', etc.
    """
    current_dir = os.path.dirname(file_path)
    
    # Loop upwards until we hit the root
    while current_dir != "":
        potential_readme = f"{current_dir}/README.md"
        # Remove leading slash if present
        if potential_readme.startswith("/"):
            potential_readme = potential_readme[1:]
            
        if potential_readme in repo_file_list:
            return potential_readme
        
        # Go up one folder
        current_dir = os.path.dirname(current_dir)
        
    return "README.md"