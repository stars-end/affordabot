#!/usr/bin/env python3
import sys
import json
import os

def load_jsonl(filename):
    items = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass # Ignore corrupted lines
    except FileNotFoundError:
        pass
    return items

def merge_jsonl(ancestor_file, current_file, other_file):
    # Load all items
    # ancestor = {item.get('id'): item for item in load_jsonl(ancestor_file) if 'id' in item}
    current_items = load_jsonl(current_file)
    other_items = load_jsonl(other_file)
    
    current_map = {item.get('id'): item for item in current_items if 'id' in item}
    other_map = {item.get('id'): item for item in other_items if 'id' in item}
    
    # Union of keys
    all_keys = set(current_map.keys()) | set(other_map.keys())
    
    merged_list = []
    
    # Sort keys to maintain stable order
    for key in sorted(all_keys):
        c_item = current_map.get(key)
        o_item = other_map.get(key)
        
        if c_item and not o_item:
            merged_list.append(c_item)
        elif o_item and not c_item:
            merged_list.append(o_item)
        else:
            # Both exist. Compare timestamps.
            c_time = c_item.get('updated_at', '')
            o_time = o_item.get('updated_at', '')
            
            # If current is newer or equal, take current
            if c_time >= o_time:
                merged_list.append(c_item)
            else:
                merged_list.append(o_item)
    
    # Write back to current_file (Git expects the result in the second argument file)
    with open(current_file, 'w') as f:
        for item in merged_list:
            f.write(json.dumps(item) + '\n')
            
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)
        
    ancestor = sys.argv[1]
    current = sys.argv[2]
    other = sys.argv[3]
    
    sys.exit(merge_jsonl(ancestor, current, other))
