import requests
import time
import json
from math import sqrt

MODEL = "llama3.2"
OLLAMA_URL = "http://localhost:11434/api/generate"
SYSTEM = "You are a document processing assistant for a title insurance company. Your job is to extract structured data from legal property documents for internal business use. Always follow instructions precisely and extract requested information directly."
N_RUNS = 20

test_cases = [
    {
        "id": "TC001",
        "description": "Extract property address",
        "strict": True,
        "prompt": "Extract the property address from this text. Respond with just the address, nothing else.\n\nText: 'This deed certifies that the property located at 842 Elm Street, Austin, TX 78701 has been transferred to Johannes Makarov.'",
        "expected_keywords": ["842 Elm Street", "Austin", "TX", "78701"],
    },
    {
        "id": "TC002",
        "description": "Extract buyer name",
        "strict": True,
        "prompt": "Extract the buyer's name from this text. The buyer is the person receiving the property transfer. Respond with just the name, nothing else.\n\nText: 'This deed certifies that the property located at 842 Elm Street, Austin, TX 78701, owned previously by Mikhail Ivanov has been transferred to Johannes Makarov.'",
        "expected_keywords": ["Johannes Makarov"],
        "forbidden_keywords": ["Mikhail", "Ivanov"],
    },
    {
        "id": "TC003",
        "description": "Identify document type",
        "strict": True,
        "prompt": "What type of legal document is this? Respond in 1-3 words only.\n\nText: 'This deed certifies transfer of property ownership from Mikhail Ivanov to Johannes Makarov, recorded this day with the county clerk.'",
        "expected_keywords": ["deed", "property deed", "warranty deed"],
    },
    {
        "id": "TC004",
        "description": "Flag missing information",
        "prompt": "Does this property record contain a sale price? Answer only 'yes' or 'no'.\n\nText: 'Property at 910 Oak Ave transferred from Robert Lee to Maria Gonzalez on March 3, 2024. No consideration stated.'",
        "expected_keywords": ["no"],
    },
    {
        "id": "TC005",
        "description": "Extract date",
        "strict": True,
        "prompt": "Extract the transfer date from this text. Respond with just the date, nothing else.\n\nText: 'This title transfer was executed on November 14, 2023, between the parties listed herein.'",
        "expected_keywords": ["November 14, 2023", "Nov 14, 2023", "11/14/2023"],
    },
]

def call_model(prompt):
    start = time.time()
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM,
        "stream": False
    }
    response = requests.post(OLLAMA_URL, json=payload)
    latency = round(time.time() - start, 2)
    result = response.json()
    return result["response"].strip(), latency

def score(response, expected_keywords, strict=False, forbidden_keywords=None):
    response_lower = response.lower().strip()

    if forbidden_keywords:
        for forbidden in forbidden_keywords:
            if forbidden.lower() in response_lower:
                return "CONTAMINATED" # sigh

    for keyword in expected_keywords:
        if keyword.lower() in response_lower:
            if strict and len(response_lower) > len(keyword) + 20:
                return "SLOPPY"  # too much extra text
            return True
    return False

def run_evals():
    print(f"\n{'='*55}")
    print(f"  TRG AI Agent Eval Harness — Model: {MODEL}")
    print(f"{'='*55}\n")

    all_run_scores = []
    per_test_success = {tc["id"]: 0 for tc in test_cases}
    all_results = []

    for run in range(N_RUNS):
        print(f"\nRun {run+1}/{N_RUNS}")
        results = []
        for tc in test_cases:
            print(f"Running {tc['id']}: {tc['description']}")
            response, latency = call_model(tc["prompt"])
            passed = score(response, tc["expected_keywords"], strict=tc.get("strict", False), forbidden_keywords=tc.get("forbidden_keywords"))
            results.append({**tc, "response": response, "latency": latency, "passed": passed})
            all_results.append({"run": run + 1, **tc, "response": response, "latency": latency, "passed": passed
})
            if passed is True:
                per_test_success[tc["id"]] += 1
            status = "PASS" if passed is True else ("SLOPPY" if passed == "SLOPPY" else "BOOOOOOO")
            print(f"  {status} | Response: '{response}' | Latency: {latency}s\n")
        passed_count = sum(1 for r in results if r["passed"] is True)
        accuracy = passed_count / len(results)
        all_run_scores.append(accuracy)

    accuracies = [a * 100 for a in all_run_scores]

    mean_acc = sum(accuracies) / len(accuracies)

    variance = sum((a - mean_acc) ** 2 for a in accuracies) / len(accuracies)
    std_acc = sqrt(variance)

    print(f"{'='*55}")
    print("STABILITY REPORT")
    print(f"{'='*55}")
    print(f"Mean Accuracy : {mean_acc:.1f}%")
    print(f"Std Accuracy  : {std_acc:.1f}%")
    print(f"Min Accuracy  : {min(accuracies):.1f}%")
    print(f"Max Accuracy  : {max(accuracies):.1f}%")

    print("\nPER-TEST SUCCESS RATES")
    print(f"{'='*55}")

    for tc in test_cases:
        rate = 100 * per_test_success[tc["id"]] / N_RUNS
        print(f"{tc['id']} ({tc['description']}): {rate:.1f}%")

    failure_counts = {}

    for r in all_results:
        if r["passed"] is False:
            failure_counts[r["id"]] = failure_counts.get(r["id"], 0) + 1

    if failure_counts:
        print("\nFAILURE MODES:")
        for tc in test_cases:
            count = failure_counts.get(tc["id"], 0)
            if count:
                print(f"  - {tc['id']} ({tc['description']}): " f"{count}/{N_RUNS} failures")

    summary = {
        "model": MODEL,
        "runs": N_RUNS,
        "mean_accuracy": mean_acc,
        "std_accuracy": std_acc,
        "min_accuracy": min(accuracies),
        "max_accuracy": max(accuracies),
        "per_test_success_rates": {
            tc["id"]: 100 * per_test_success[tc["id"]] / N_RUNS
            for tc in test_cases
        }
    }
    with open("eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("  Full results saved to eval_results.json\n")

if __name__ == "__main__":
    run_evals()