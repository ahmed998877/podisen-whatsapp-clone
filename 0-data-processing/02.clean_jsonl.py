import json

def clean_jsonl(input_file, output_file):
    # Read the input file
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Process each line
    cleaned_lines = []
    for line in lines:
        try:
            data = json.loads(line)
            # Check if the line has both user and model roles
            has_user = False
            has_model = False
            
            for content in data.get('contents', []):
                if content.get('role') == 'user':
                    has_user = True
                elif content.get('role') == 'model':
                    has_model = True
                
                # If we found both roles, we can stop checking
                if has_user and has_model:
                    break
            
            # Only keep lines that have both roles
            if has_user and has_model:
                cleaned_lines.append(line)
                
        except json.JSONDecodeError:
            print(f"Error parsing line: {line}")
            continue
    
    # Write the cleaned data to the output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)
    
    print(f"Original lines: {len(lines)}")
    print(f"Cleaned lines: {len(cleaned_lines)}")
    print(f"Removed lines: {len(lines) - len(cleaned_lines)}")

if __name__ == "__main__":
    input_file = "whatsapp_data/clean/train_data_emjFixed.jsonl"
    output_file = "whatsapp_data/clean/train_data_emjFixed_cleaned.jsonl"
    clean_jsonl(input_file, output_file) 