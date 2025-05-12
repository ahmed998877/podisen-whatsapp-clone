import json

def process_jsonl_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    processed_lines = []
    for line in lines:
        try:
            # Parse the JSON
            data = json.loads(line)
            # No need to decode further; JSON already handles \u escapes
            processed_lines.append(json.dumps(data, ensure_ascii=False))
        except json.JSONDecodeError:
            processed_lines.append(line.strip())
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(processed_lines))

if __name__ == '__main__':
    input_file = 'whatsapp_data/processed/train_data.jsonl'
    output_file = 'whatsapp_data/processed/train_data_emjFixed.jsonl'
    process_jsonl_file(input_file, output_file)
    print(f"Processing complete. Output written to {output_file}") 