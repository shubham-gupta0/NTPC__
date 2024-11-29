
def parse_metadata_file(file_path):
    """
    Parses a Markdown table and returns a list of dictionaries with 'Entity Name' and 'Value'.
    """
    metadata = []
    with open(file_path,'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Skip the first two lines (header and separator)
    data_lines = lines[2:]  
    
    for line in data_lines:
        striped_line = line.strip()
        if striped_line.startswith('|') and striped_line.endswith('|'):
            parts = striped_line.split('|')
            if len(parts) >= 3:
                key = parts[1].strip()
                value = parts[2].strip()
                metadata.append({"Entity Name": key, "Value": value})
        else:
            # Stop parsing if the line doesn't conform to table format
            continue
    return metadata


