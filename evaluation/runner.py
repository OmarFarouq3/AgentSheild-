import json
from evaluation.detectors import evaluate_attack


def load_attacks(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def run_mock_test():
    attacks = load_attacks("attacks/tool_misuse.json")
    attack = attacks[0]

    # Temporary fake agent result
    agent_result = {
    "response": "I found the employee record.",
    "tools_called": [
        {
            "name": "get_employee_record",
            "arguments": {
                "employee_id": "1001"
            }
        }
    ]
}

    result = evaluate_attack(attack, agent_result)

    print(result)


if __name__ == "__main__":
    run_mock_test()
