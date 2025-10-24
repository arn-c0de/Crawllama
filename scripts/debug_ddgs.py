"""Quick test to see what ddgs returns."""
from ddgs import DDGS

print("Testing DDGS...")

try:
    with DDGS() as ddgs:
        results = ddgs.text("test", max_results=2, region="de-de")

        print(f"\nGot {len(list(results))} results")

        # Re-run to actually inspect
        results = ddgs.text("test", max_results=2, region="de-de")
        for i, r in enumerate(results, 1):
            print(f"\n=== Result {i} ===")
            print(f"Type: {type(r)}")
            print(f"Keys: {r.keys() if isinstance(r, dict) else 'N/A'}")
            if isinstance(r, dict):
                for key, value in r.items():
                    print(f"  {key}: {value[:100] if isinstance(value, str) else value}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
