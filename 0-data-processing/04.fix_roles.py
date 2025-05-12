import json

input_path = "whatsapp_data/final/train_data_emjFixed_cleaned.jsonl"
output_path = "whatsapp_data/final/train_data_emjFixed_cleaned_fixed.jsonl"

def merge_consecutive_roles(contents):
    if not contents:
        return contents
    merged = [contents[0]]
    for turn in contents[1:]:
        if turn["role"] == merged[-1]["role"]:
            # Merge parts
            merged[-1]["parts"][0]["text"] += "\n" + turn["parts"][0]["text"]
        else:
            merged.append(turn)
    return merged

with open(input_path, "r", encoding="utf-8") as infile, open(output_path, "w", encoding="utf-8") as outfile:
    for line in infile:
        data = json.loads(line)
        data["contents"] = merge_consecutive_roles(data["contents"])
        outfile.write(json.dumps(data, ensure_ascii=False) + "\n")

print("Done! Fixed file saved as:", output_path) 