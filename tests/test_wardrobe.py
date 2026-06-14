from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

query = "vintage graphic tee under $30"

print("=== WITH example wardrobe ===")
s1 = run_agent(query, get_example_wardrobe())
print(s1["outfit_suggestion"])

print("\n=== WITH empty wardrobe ===")
s2 = run_agent(query, get_empty_wardrobe())
print(s2["outfit_suggestion"])
